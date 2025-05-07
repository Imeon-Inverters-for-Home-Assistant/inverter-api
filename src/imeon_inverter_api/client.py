import aiohttp
from aiohttp import FormData, client_exceptions
import logging
import asyncio
from typing import Any, Dict, Callable, List, Literal
from functools import wraps
import time
from json import loads, dumps

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(encoding='utf-8',
                    level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s : %(message)s') # filename=f'{__name__}.log',

# credit to : https://dev.to/kcdchennai/python-decorator-to-measure-execution-time-54hk
def timed(func: Callable) -> Callable:
    """Measure time of execution for async functions."""
    @wraps(func)
    async def time_wrapper(*args, **kwargs) -> ... :
        start_time = time.perf_counter()
        _LOGGER.debug(f'Function {func.__qualname__}{args} {kwargs} call starts now')
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        _LOGGER.debug(f'Function {func.__qualname__}{args} {kwargs} took {total_time:.4f} seconds\n')
        return result
    return time_wrapper


class Client():

    """
    Client to connect to securely connect to the inverter and request
    data through POST/GET requests.
    """

    TIMEOUT = 15           # seconds
    TIMEOUT_POST = 20      # seconds
    BOTTLENECK = True      # Bottleneck acts as Rate Limiter
    BOTTLENECK_SIZE = 1    # "Queue" size
    BOTTLENECK_RATE = 1.2  # seconds
    DEPRECATED_API = False # Use only the older API methods

    def __init__(self, ip: str):
        self._IP : str = ip
        self.__session : aiohttp.ClientSession | None = None
        self._queue : asyncio.Queue = asyncio.Queue(self.BOTTLENECK_SIZE)

    def __del__(self) -> None:
        """Close client connection when this object is destroyed."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close_session())
            else:
                loop.run_until_complete(self.close_session())
        except RuntimeError:
            asyncio.run(self.close_session()) # Hideous workaround not using context managers
        except Exception as e:
            _LOGGER.error(f"Error while closing: {e}")
        finally:
            _LOGGER.debug(f"Closed Client session")

    async def __adel__(self) -> None:
        """Close client connection when this object is destroyed (async)."""
        await self.close_session()

    # CONTEXT MANAGER #
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        del self

    # ASYNC CONTEXT MANAGER #
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self.__adel__()


    async def get_session(self) -> aiohttp.ClientSession | None:
        """Get the currently saved session."""
        return self.__session

    async def init_session(self, timeout: int = TIMEOUT) -> None:
        """Initialize the aiohttp session if needed."""
        if self.__session is None or self.__session.closed:
            self.__session = aiohttp.ClientSession()

    async def keep_session_alive(self) -> None:
        """Keep an aiohttp session alive and pass down cookies through sessions."""
        if self.__session.closed:
            cookies = self.get_session_cookies()
            self.__session = aiohttp.ClientSession()
            self.__session.cookie_jar.update_cookies(cookies)

    async def close_session(self) -> None:
        """Close the current aiohttp session."""
        if self.__session and not self.__session.closed:
            await self.__session.close()

    def get_session_cookies(self) -> Dict[Any, None]:
        """Get the authentication cookies for this session."""
        cookies = {}
        for cookie in self.__session.cookie_jar:
            cookies[cookie.key] = cookie.value
        return cookies

    # ============== #
    # HELPER METHODS #
    # ============== #

    @property
    async def _bottleneck(self) -> None:
        """Place a timer in queue to slow down requests."""
        await self._queue.put(time.perf_counter())

    async def task(self, func: Callable, url: str, data: str) -> Any | None:
        """Bottleneck the amount of requests sent out, in speed and volume."""
        await self._bottleneck # Place in queue, wait if there's no spot

        # Call function with proper error handling
        try:
            task = await func(url, data=data)
        except client_exceptions.ClientConnectorDNSError as e:
            raise ValueError(f"Host invalid: {e}") from e
        except client_exceptions.ClientConnectorError as e:
            raise ValueError(f"Route invalid: {e}")
        except Exception as e:
            raise Exception(f"Task {func} failed: {e} \nRequest @ {url}") from e

        # Calculate time elapsed during call
        start_time = await self._queue.get()
        end_time = time.perf_counter()
        elapsed = end_time - start_time

        # Wait to match the imposed bottleneck rate
        await asyncio.sleep(max(self.BOTTLENECK_RATE - elapsed, 0))

        return task

    def build_request(self, *, method : Literal['POST', 'GET'] = 'GET',
                      url: str, data: str | FormData, timeout: float = TIMEOUT) -> Callable:
        """Decorate async requests with automatic timeout and error handling."""

        def __decorator__(func: Callable):

            @wraps(func)
            async def __wrapper__(**kwargs) -> ... :
                _LOGGER.debug(f"| Request Wrapper: {url} {str(data)[:50] + ' ...' if len(str(data))>50 else str(data)}")

                # Check for session
                await self.keep_session_alive()

                try:
                    # Do POST/GET request and store the response with timeout
                    task = self.task(self.__session.post, url, data) if method == 'POST' \
                           else self.task(self.__session.get, url, data)
                    call_task = asyncio.create_task(task)
                    task_result = await asyncio.wait_for(call_task, timeout)

                    # Handle timeouts through async context managers
                    async with task_result as response:
                        __wrapper__.response = response # Store response as a function attribute
                        return await func(**kwargs)

                except aiohttp.ClientError as e:
                    # Handle client errors (e.g., connection issues)
                    raise  aiohttp.ClientError(f"Error making {method} request: {e} \nRequest @ {url}\nPayload   {data}") from e
                except asyncio.TimeoutError as e:
                    # Handle timeout
                    raise TimeoutError(f"{method} request timed out. Check the IP configuration of the inverter.") from e
                except ValueError as e:
                    # Handle invalid host or invalid route
                    raise ValueError(e) from e
                except Exception as e:
                    # Other errors go here
                    raise Exception(f"{method} request failed: {e} \nRequest @ {url}") from e

            return __wrapper__
        return __decorator__

    # =============== #
    # IMEON API CALLS #
    # =============== #

    @timed
    async def login(self, username: str, password: str, timeout: int = TIMEOUT,
                    check: bool = False) -> Dict[str, Any] | None:
        """Connect to IMEON API using POST HTTP protocol."""
        url = self._IP

        await self.init_session()

        # Build request payload
        url = "http://" + url + "/login"
        data = {
            "do_login" : not check,
            "email" : username,
            "passwd": password
        }

        @self.build_request(method="POST", url=url, data=data, timeout=timeout)
        async def _request():
            json = await _request.response.json()
            if not check:
                # Store the session token in session for later uses
                cookies = _request.response.cookies
                self.__session.cookie_jar.update_cookies(cookies)
            return json

        return await _request()

    # POST REQUESTS #

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

        # Build request payload
        urls = {"data"  : "http://" + url + "/data",
                "scan"  : "http://" + url + "/scan?scan_time=&single=true",
                "status": "http://" + url + "/imeon-status"}
        url = urls[info_type]
        data = ""

        @self.build_request(method="GET", url=url, data=data, timeout=timeout)
        async def _request():
            json = await _request.response.json()
            return json

        return await _request()

    async def get_serial(self) -> str:
        """Get the inverter serial."""
        data = await self.get_data_instant("data")
        return data["serial"]

    async def get_data_onetime(self) -> Dict[str, float]:
        """Gather one-time data from IMEON API using GET HTTP protocol."""
        data = await self.get_data_instant("data")
        json = {}
        json["inverter"] = data["type"]
        json["software"] = data["software"]
        json["serial"] = data["serial"]
        json["charging_current_limit"] = data["max_ac_charging_current"]
        json["injection_power_limit"] = data["injection_power"]
        json["battery_night_discharge"] = (data["enable_status"].get("discharge_night") == "1")
        json["battery_grid_charge"] = (data["enable_status"].get("charge_bat_with_grid") == "1")
        return json

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
        assert time in ('minute', 'quarter'), "Valid times are: 'minute', 'quarter'"
        url = self._IP

        urls = {
            "battery" : "http://" + url + "/api/battery",
            "grid"    : "http://" + url + "/api/grid?threephase=true",
            "pv"      : "http://" + url + "/api/pv",
            "input"   : "http://" + url + "/api/input",
            "output"  : "http://" + url + "/api/output?threephase=true",
            "meter"   : "http://" + url + "/api/em",
            "temp"    : "http://" + url + "/api/temp",
            "energy"  : "http://" + url + "/api/energy"
            }
        suffix = "?time={}".format(time)
        data = ""

        json = {}

        # Loop through the URLs
        for key, url in urls.items():
            url = url + suffix

            @self.build_request(method="GET", url=url, data=data, timeout=timeout)
            async def _request():
                json[key] = await _request.response.json()
                json[key]["result"] = loads(json[key]["result"])

            await _request()

        return json

    @timed
    async def get_data_monitoring(self, time="hour",
                                  timeout: int = TIMEOUT) -> Dict[str, float] | None:
        """
        Gather monitoring data from IMEON API using GET HTTP protocol.

            Note: this is mostly meant to be used for a supervision screen,
                  so using time intervals longer than hours is recommended
                  for more sensible data collection.
        """
        url = self._IP

        # Build request payload
        url = "http://" + url + "/api/monitor?time={}".format(time)
        data = ""

        @self.build_request(method="GET", url=url, data=data, timeout=timeout)
        async def _request():
            json = await _request.response.json()
            json["result"] = loads(json["result"])
            return json

        return await _request()

    @timed
    async def get_data_manager(self, timeout: int = TIMEOUT) -> Dict[str, float] | None:
        """Gather relay and state data from IMEON API using GET HTTP protocol."""
        url = self._IP

        # Build request payload
        url = "http://" + url + "/api/manager"
        data = ""

        @self.build_request(method="GET", url=url, data=data, timeout=timeout)
        async def _request():
            json = await _request.response.json()
            json["result"] = loads(json["result"])
            return json

        return await _request()

    @timed
    async def get_data_smartload(self, timeout: int = TIMEOUT) -> Dict[str, float] | None:
        """Gather relay and state data from IMEON API using GET HTTP protocol."""
        url = self._IP

        # Build request payload
        url = "http://" + url + "/api/smartload"
        data = ""

        @self.build_request(method="GET", url=url, data=data, timeout=timeout)
        async def _request():
            json = await _request.response.json()
            json["result"] = loads(json["result"])
            return json

        return await _request()

    # POST REQUESTS #

    @timed
    async def set_from_dict(self, inputs: dict, perform_save: bool = False,
                  timeout: int = TIMEOUT_POST) -> bool | None:
        """
        Send data changes to IMEON API using HTTP POST.

        "inputs" can contains the following fields:
            inverter_mode   : <str> (smg | bup | ong | ofg)
            mppt            : [<int>, <int>]
            feed_in         : <bool>
            injection_power : <int>
            lcd_time        : <int>
            date            : <str> (yyyy/mm/ddhh:mm)
            night_discharge : <bool>
            grid_charge     : <bool>
            relay_active    : <bool>
            ac_output_active: <bool>
        """

        # Build request payload
        url = self._IP
        url = "http://" + url + "/api/set"
        data = FormData()
        for k, v in inputs.items():
            data.add_field(str(k), str(v))
        data.add_field('permasave', perform_save)

        @self.build_request(method="POST", url=url, data=data, timeout=timeout)
        async def _request():
            text = await _request.response.text()
            return text

        return await _request()

# ===== #
# TESTS #
# ===== #

if __name__ == "__main__":
    import asyncio

    _LOGGER.debug('Start of tests\n')


    async def login_test() -> None:
        c = Client("192.168.200.184")

        response = await c.login('installer@local', 'Installer_P4SS')

        _LOGGER.debug(response)


    async def get_test() -> dict:
        c = Client("192.168.200.184")

        await c.login('user@local', 'password')

        data = []
        data.append(await c.get_data_onetime())
        data.append(await c.get_data_timed('quarter'))
        data.append(await c.get_data_manager())
        data.append(await c.get_data_monitoring('minute'))
        data.append(await c.get_data_monitoring())
        data.append(await c.get_data_timeline())

        for datum in data:
            d = dumps(datum, indent=2, sort_keys=True)
            _LOGGER.debug(d)


    async def post_test() -> None:
        c = Client("192.168.200.184")

        await c.login('installer@local', 'Installer_P4SS')

        response = await c.set_from_dict({"relay_active": False})
        _LOGGER.debug(response)

    async def context_test() -> None:
        with Client("192.168.200.184") as c:
            await c.login('installer@local', 'Installer_P4SS')

    async def async_context_test() -> None:
        async with Client("192.168.200.184") as c:
            await c.login('installer@local', 'Installer_P4SS')

    async def smartload_test() -> None:
        with Client("192.168.200.184") as c:
            await c.login("user@local", "password")
            smtld = await c.get_data_smartload()
            _LOGGER.debug(smtld)

    async def print_doc() -> None:
        import pydoc
        strhelp = pydoc.render_doc(Client, "Help on %s")
        print(strhelp)

    asyncio.run(get_test())
    _LOGGER.debug('End of tests')
