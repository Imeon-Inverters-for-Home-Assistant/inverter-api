if __name__ == "__main__": 
    from client import Client
else:
    from imeon_inverter_api.client import Client

class Inverter():

    """
    Client data organised as a class storing the collected data, 
    with methods allowing periodical updates. Meant for use in
    supervision tools (such as Home Assistant).

        Note: for manual access, here's the storage structure
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
                    "timeline": [{}]
                }
    """

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
            "timeline": [{}]
        }
        return None
    
    async def login(self, username: str, password: str) -> None:
        """Request client login. See Client documentation for more details."""
        if self.__auth_valid == False:
            try:
                await self._client.login(username, password)
                self.__auth_valid = True
            except Exception as e:
                raise Exception(f"Error while checking credentials: {e}")
            
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
        except Exception as e:
            raise e
        
        for key in ["battery", "grid", "pv", "input", "output", "temp", "meter"]:
            storage[key] = data_timed.get(key, {}).get("result", {})

        storage["monitoring"] = data_monitoring.get("result", {})
        storage["monitoring_minute"] = data_monitoring_minute.get("result", {})
        storage["manager"] = data_manager.get("result", {})
        storage["timeline"] = data_timeline

    
    async def init(self) -> None:
        """Request a data initialisation from the Client. Collects "one-time" data."""
        try:
            await self.update()
            data_inverter = await self._client.get_data_onetime()
        except Exception as e:
            raise e

        self._storage["inverter"] = data_inverter

    async def get_address(self) -> str | None:
        """Returns client IP."""
        return self._client._IP

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
    
            
if __name__ == "__main__":
    import asyncio
    import json

    # Tests
    async def _test():
        i = Inverter("192.168.200.86")
        await i.login("user@local", "password")
        await i.init()
        print(json.dumps(i._storage, indent=2, sort_keys=True))

    asyncio.run(_test())