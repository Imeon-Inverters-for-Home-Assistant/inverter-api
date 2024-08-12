import aiohttp
import async_timeout
import asyncio
from typing import Any, Dict, Callable, List
from functools import wraps
import time
from json import loads, dumps

# credit to : https://dev.to/kcdchennai/python-decorator-to-measure-execution-time-54hk
def timed(func: Callable) -> Callable:
    """Measure time of execution for async functions."""
    @wraps(func)
    async def time_wrapper(*args, **kwargs) -> Any | None:
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(f'Function {func.__qualname__}{args} {kwargs} Took {total_time:.4f} seconds')
        return result
    return time_wrapper

class Client():

    """
    Client to connect to securely connect to the inverter and request data.
    """

    TIMEOUT = 10
    BOTTLENECK = True # Bottleneck acts as Rate Limiter
    BOTTLENECK_SIZE = 1
    BOTTLENECK_RATE = 1.2

    def __init__(self, ip: str):
        self._IP : str = ip
        self.__session : aiohttp.ClientSession | None = None
        self._queue : asyncio.Queue = asyncio.Queue(self.BOTTLENECK_SIZE) 

    async def get_session(self) -> aiohttp.ClientSession | None:
        """Get the currently saved session."""
        return self.__session

    async def init_session(self) -> None:
        """Initialize the aiohttp session."""
        if self.__session is None or self.__session.closed:
            self.__session = aiohttp.ClientSession()

    async def keep_session_alive(self) -> None:
        """Initialize the aiohttp session."""
        if self.__session.closed:
            cookies = self.get_session_cookies()
            self.__session = aiohttp.ClientSession()
            self.__session.cookie_jar.update_cookies(cookies)
    
    async def close_session(self) -> None:
        """Close the aiohttp session."""
        if self.__session and not self.__session.closed:
            await self.__session.close()

    def get_session_cookies(self) -> Dict[Any, None]:
        """Get the authentication cookies for this session."""
        cookies = {}
        for cookie in self.__session.cookie_jar:
            cookies[cookie.key] = cookie.value
        return cookies
    
    @property
    async def _bottleneck(self) -> None:
        """Place a timer in queue to slow down requests."""
        await self._queue.put(time.perf_counter())
    
    async def task(self, func: Callable, url: str, data: str) -> Any | None:
        """Bottleneck the amount of requests sent out, in speed and volume."""
        await self._bottleneck

        try:
            task = await func(url, data=data)
        except Exception as e:
            raise Exception(f"Task {func} failed: {e} \nRequest @ {url}")
        start_time = await self._queue.get()
        end_time = time.perf_counter()

        elapsed = end_time - start_time
        #print(elapsed)
        await asyncio.sleep(max(self.BOTTLENECK_RATE - elapsed, 0))

        return task
    
    # IMEON API CALLS #
    @timed
    async def login(self, username: str, password: str, timeout: int = TIMEOUT, 
                    check: bool = False) -> Dict[str, Any] | None:
        """Connect to IMEON API using POST HTTP protocol."""
        url = self._IP
        
        await self.init_session()
        session = self.__session

        # Build request payload
        url = "http://" + url + "/login"
        data = {
            "do_login" : not check,
            "email" : username,
            "passwd": password
        }

        try:
            task = await self.task(session.post, url, data)

            async with async_timeout.timeout(timeout):
                async with task as response:
                    json = await response.json()
                    if not check: 
                        cookies = response.cookies
                        # Store the session token in session for later uses
                        self.__session.cookie_jar.update_cookies(cookies)
                    return json
        except aiohttp.ClientError as e:
            # Handle client errors (e.g., connection issues)
            raise Exception(f"Error making POST request: {e} \nRequest @ {url}\nPayload   {data}")
        except asyncio.TimeoutError:
            # Handle timeout
            raise Exception("POST request timed out. Check the IP configuration of the inverter.")
        except Exception as e:
                raise Exception(f"POST request failed: {e} \nRequest @ {url}")
    
    @timed
    async def get_data_onetime(self) -> Dict[str, float]:
        """Gather one-time data from IMEON API using GET HTTP protocol."""
        data = await self.get_data_instant("data")
        json = {}
        json["inverter"] = data["type"]
        json["software"] = data["software"]
        json["serial"] = data["serial"]
        json["charging_current_limit"] = data["max_ac_charging_current"]
        json["injection_power_limit"] = data["injection_power"]
        return json
    
    @timed
    async def get_data_timeline(self) -> List[Dict[str, None]]:
        """Gather timeline data from IMEON API using GET HTTP protocol."""
        data = await self.get_data_instant("status")
        list = data.get("state_timeline", {}).get("detail", [{}])
        return list

    @timed
    async def get_data_timed(self, time: str = 'minute', 
                             timeout: int = TIMEOUT) -> Dict[str, float] | None: 
        """
        Gather minute data from IMEON API using GET HTTP protocol.
        
            Note: this call is quite slow even without rate limiting, use
                  get_data_instant() if you're interested in collecting
                  a lot of data at once.
        """
        assert time in ('minute', 'quarter', 'hour','day', 'week', 'month', 'year'), \
            "Valid times are: 'minute', 'quarter', 'hour', 'day', 'week', 'month', 'year'"
        url = self._IP
        
        await self.keep_session_alive()
        session = self.__session

        urls = {
            "battery" : "http://" + url + "/api/battery", 
            "grid"    : "http://" + url + "/api/grid?threephase=true",
            "pv"      : "http://" + url + "/api/pv",
            "input"   : "http://" + url + "/api/input",
            "output"  : "http://" + url + "/api/output?threephase=true",
            "meter"   : "http://" + url + "/api/em",
            "temp"    : "http://" + url + "/api/temp"
            }
        suffix = "?time={}".format(time)
        
        json = {} 

        # Loop through the requests
        for key, url in urls.items():
            try:
                task = await self.task(session.get, url + suffix, "")
                json[key] = {}
            
                async with async_timeout.timeout(timeout):
                    async with task as response:
                        #return await response.json()
                        json[key] = await response.json()
                        json[key]["result"] = loads(json[key]["result"])
            except aiohttp.ClientError as e:
                # Handle client errors (e.g., connection issues)
                raise Exception(f"Error making GET request: {e} \nRequest @ {url}")
            except asyncio.TimeoutError:
                # Handle timeout
                raise Exception("GET request timed out. Check the IP configuration of the inverter.")
            except Exception as e:
                raise Exception(f"GET request failed: {e} \nRequest @ {url}")
        
        return json

    @timed
    async def get_data_monitoring(self, time="day", 
                                  timeout: int = TIMEOUT) -> Dict[str, float] | None: 
        """
        Gather monitoring data from IMEON API using GET HTTP protocol.
        
            Note: this is mostly meant to be used for a supervision screen,
                  so using time intervals longer than hours is recommended
                  for more sensible data collection.
        """
        url = self._IP

        await self.keep_session_alive()
        session = self.__session

        # Build request payload
        url = "http://" + url + "/api/monitor?time={}".format(time)

        try:
            task = await self.task(session.get, url, "")
        
            async with async_timeout.timeout(timeout):
                async with task as response:
                    json = await response.json()
                    json["result"] = loads(json["result"])
                    return json
        except aiohttp.ClientError as e:
            # Handle client errors (e.g., connection issues)
            raise Exception(f"Error making GET request: {e} \nRequest @ {url}")
        except asyncio.TimeoutError:
            # Handle timeout
            raise Exception("GET request timed out. Check the IP configuration of the inverter.")
        except Exception as e:
            raise Exception(f"GET request failed: {e} \nRequest @ {url}")

    @timed
    async def get_data_manager(self, timeout: int = TIMEOUT) -> Dict[str, float] | None: 
        """Gather relay and state data from IMEON API using GET HTTP protocol."""
        url = self._IP

        await self.keep_session_alive()
        session = self.__session

        # Build request payload
        url = "http://" + url + "/api/manager"

        try:
            task = await self.task(session.get, url, "")
        
            async with async_timeout.timeout(timeout):
                async with task as response:
                    json = await response.json()
                    json["result"] = loads(json["result"])
                    return json
        except aiohttp.ClientError as e:
            # Handle client errors (e.g., connection issues)
            raise Exception(f"Error making GET request: {e} \nRequest @ {url}")
        except asyncio.TimeoutError:
            # Handle timeout
            raise Exception("GET request timed out. Check the IP configuration of the inverter.")
        except Exception as e:
            raise Exception(f"GET request failed: {e} \nRequest @ {url}")

    @timed
    async def get_data_instant(self, info_type: str = "data", 
                               timeout: int = TIMEOUT) -> Dict[str, Any] | Any | None: 
        """
        Gather instant data from IMEON API using GET HTTP protocol.
        
            Note: this gathers a large amount of instant data at once,
                  it is advised to only use this when you need all
                  the collected data quickly.
        """
        assert info_type in ('data', 'scan', 'status'), "Valid info types are: 'data', 'scan', 'status'"
        url = self._IP

        await self.keep_session_alive()
        session = self.__session

        # Build request payload
        urls = {"data"  : "http://" + url + "/data", 
                "scan"  : "http://" + url + "/scan?scan_time=&single=true",
                "status": "http://" + url + "/imeon-status"} 
        
        try:
            task = await self.task(session.get, urls[info_type], data="")
        
            async with async_timeout.timeout(timeout):
                async with task as response:
                    json = await response.json()
                    return json
        except aiohttp.ClientError as e:
            # Handle client errors (e.g., connection issues)
            raise Exception(f"Error making GET request: {e} \nRequest @ {url}")
        except asyncio.TimeoutError:
            # Handle timeout
            raise Exception("GET request timed out. Check the IP configuration of the inverter.")
        except Exception as e:
            raise Exception(f"GET request failed: {e} \nRequest @ {url}")
    
    # TODO post requests methods

    # ASYNC HANDLERS #
    def __del__(self) -> None:
        """Close client connection when this object is destroyed."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close_session())
            else:
                loop.run_until_complete(self.close_session())
        except Exception as e:
            pass # Let session close itself and generate an error

if __name__ == "__main__":
    import asyncio
    import json

    # Tests
    async def dataset_test() -> dict:
        c = Client("192.168.200.110")

        await c.login('user@local', 'password')

        data = []
        data.append(await c.get_data_onetime())
        data.append(await c.get_data_timed('hour'))
        data.append(await c.get_data_manager())
        data.append(await c.get_data_monitoring())
        data.append(await c.get_data_timeline())

        for datum in data:
            d = dumps(datum, indent=2, sort_keys=True)
            print(d)

    asyncio.run(dataset_test())