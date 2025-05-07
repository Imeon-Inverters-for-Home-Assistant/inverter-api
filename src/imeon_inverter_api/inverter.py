from typing import Literal, Tuple
from typing_extensions import Annotated
from aiohttp import ClientError

if __name__ == "__main__":
    from client import Client, _LOGGER
else:
    from imeon_inverter_api.client import Client, _LOGGER

class Inverter():

    """
    Client data organised as a class storing the collected data,
    with methods allowing periodical updates. Meant for use in
    supervision tools (such as Home Assistant).

        Note: for manual access, here's the storage structure
            ```
            self._storage = {
                    "battery" : {},
                    "grid": {},
                    "pv": {},
                    "input": {},
                    "output": {},
                    "meter": {},
                    "temp": {},
                    "monitoring": {},
                    "manager": {},
                    "inverter": {},
                    "timeline": [{}],
                    "smartload": {},
                    "energy": {}
                }
            ```
    """

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self._client.close_session()

    def __init__(self, address: str):
        self._client = Client(address)
        self.__auth_valid = False
        self._storage = {
            "battery" : {},
            "grid": {},
            "pv": {},
            "input": {},
            "output": {},
            "meter": {},
            "temp": {},
            "monitoring": {},
            "manager": {},
            "inverter": {},
            "timeline": [{}],
            "smartload": {},
            "energy": {}
        }
        return None

    async def login(self, username: str, password: str) -> bool:
        """Request client login. See Client documentation for more details."""
        if self.__auth_valid == False:
            try:
                response = await self._client.login(username, password)
                self.__auth_valid = True
                return response['accessGranted']
            except TimeoutError as e:
                raise TimeoutError from e
            except ValueError as e:
                raise ValueError(e) from e
            except Exception as e:
                raise Exception from e

    async def update(self) -> None:
        """Request a data update from the Client. Replaces older data, but doesn't affect "one-time" data."""
        storage = self._storage
        client = self._client

        try:
            data_timed = await client.get_data_timed()
            data_monitoring = await client.get_data_monitoring(time='hour')
            data_monitoring_minute = await client.get_data_monitoring(time='minute')
            data_manager = await client.get_data_manager()
            data_timeline = await client.get_data_timeline()
            data_smartload = await client.get_data_smartload()
        except TimeoutError as e:
            raise TimeoutError from e
        except ClientError as e:
            raise ClientError from e
        except ValueError as e:
            raise ValueError from e
        except Exception as e:
            raise Exception from e

        for key in ["battery", "grid", "pv", "input", "output", "temp", "meter", "energy"]:
            storage[key] = data_timed.get(key, {}).get("result", {})

        storage["monitoring"] = data_monitoring.get("result", {})
        storage["monitoring_minute"] = data_monitoring_minute.get("result", {})
        storage["manager"] = data_manager.get("result", {})
        storage["timeline"] = data_timeline
        storage["smartload"] = data_smartload


    async def init(self) -> None:
        """Request a data initialisation from the Client. Collects "one-time" data."""
        try:
            await self.update()
            data_inverter = await self._client.get_data_onetime()
        except TimeoutError as e:
            raise TimeoutError from e
        except Exception as e:
            raise Exception from e

        self._storage["inverter"] = data_inverter

    def get_address(self) -> str | None:
        """Returns client IP."""
        return self._client._IP

    async def get_serial(self) -> str:
        """Returns inverter serial."""
        try:
            serial = await self._client.get_serial()
            return serial
        except TimeoutError as e:
            raise TimeoutError from e

    @property
    def battery(self): return self._storage.get("battery", {})

    @property
    def grid(self): return self._storage.get("grid", {})

    @property
    def pv(self): return self._storage.get("pv", {})

    @property
    def input(self): return self._storage.get("input", {})

    @property
    def output(self): return self._storage.get("output", {})

    @property
    def meter(self): return self._storage.get("meter", {})

    @property
    def temp(self): return self._storage.get("temp", {})

    @property
    def monitoring(self): return self._storage.get("monitoring", {})

    @property
    def manager(self): return self._storage.get("manager", {})

    @property
    def inverter(self): return self._storage.get("inverter", {})

    @property
    def timeline(self): return self._storage.get("timeline", [{}])

    @property
    def smartload(self): return self._storage.get("smartload", {})

    @property
    def energy(self): return self._storage.get("energy", {})

    @property
    def storage(self): return self._storage


    async def set_inverter_mode(self, mode: Literal['smg', 'bup', 'ong', 'ofg'] = 'smg') -> bool | None:
        """Change the inverter mode to the given input."""
        return await self._client.set_from_dict(inputs = {"inverter_mode": mode})

    async def set_mppt(self, range: Tuple[int, int]) -> bool | None:
        """Change the maximum power point tracking range to the given input."""
        return await self._client.set_from_dict(inputs = {"mppt": range})

    async def set_injection_power(self, value: Annotated[int, "0 <= x"]) -> bool | None:
        """Change the injection power limit to the given input."""
        return await self._client.set_from_dict(inputs = {"injection_power": value})

    async def set_lcd_time(self, time: Annotated[int, "0 <= x <= 20"]) -> bool | None:
        """Change the LCD screen sleep time to the given input."""
        return await self._client.set_from_dict(inputs = {"lcd_time": time})

    async def set_date(self, date: Annotated[str, "Format: yyyy/mm/ddhh:mm"]) -> bool | None:
        """Change the inverter date to the given input."""
        return await self._client.set_from_dict(inputs = {"date": date})

    async def set_feed_in(self, value: bool) -> bool | None:
        """Activate/deactivate grid power injection."""
        return await self._client.set_from_dict(inputs = {"feed_in": value})

    async def set_night_discharge(self, value: bool) -> bool | None:
        """Activate/deactivate nightly discharge for the battery."""
        return await self._client.set_from_dict(inputs = {"night_discharge": value})

    async def set_grid_charge(self, value: bool) -> bool | None:
        """Activate/deactivate grid charge for the battery."""
        return await self._client.set_from_dict(inputs = {"grid_charge": value})

    async def set_relay(self, value: bool) -> bool | None:
        """Activate/deactivate the relay."""
        return await self._client.set_from_dict(inputs = {"relay_active": value})

    async def set_ac_output(self, value: bool) -> bool | None:
        """Activate/deactivate AC output."""
        return await self._client.set_from_dict(inputs = {"ac_output_active": value})


# ===== #
# TESTS #
# ===== #

if __name__ == "__main__":
    import asyncio
    import json

    async def init_test():
        i = Inverter("192.168.200.184")
        await i.login("user@local", "password")
        await i.init()
        _LOGGER.debug(json.dumps(i.storage, indent=2, sort_keys=True))

    async def update_test():
        i = Inverter("192.168.200.184")
        await i.login("user@local", "password")
        await i.update()
        _LOGGER.debug(json.dumps(i.storage, indent=2, sort_keys=True))

    async def post_test():
        i = Inverter("192.168.200.184")
        await i.login("user@local", "password")
        result = await i.set_inverter_mode('bup')
        _LOGGER.debug(result)

    async def print_doc() -> None:
        import pydoc
        strhelp = pydoc.render_doc(Inverter, "Help on %s")
        print(strhelp)

    asyncio.run(init_test())
