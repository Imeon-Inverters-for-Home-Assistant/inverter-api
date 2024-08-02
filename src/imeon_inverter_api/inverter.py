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
                    "inverter": {}
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
            "inverter": {}
        }
        return None
    
    async def login(self, username: str, password: str):
        """Request client login. See Client documentation for more details."""
        if self.__auth_valid == False:
            try:
                await self._client.login(username, password)
                self.__auth_valid = True
            except Exception as e:
                raise Exception(f"Error while checking credentials: {e}")
            
    async def update(self):
        """Request a data update from the Client. Replaces older data, but doesn't affect "one-time" data."""
        storage = self._storage
        client = self._client

        try: 
            data_timed = await client.get_data_timed()
            data_monitoring = await client.get_data_monitoring()
            data_manager = await client.get_data_manager()
        except Exception as e:
            raise e

        storage["battery"] = data_timed.get("battery", {})
        storage["grid"] = data_timed.get("grid", {})
        storage["pv"] = data_timed.get("pv", {})
        storage["input"] = data_timed.get("input", {})
        storage["output"] = data_timed.get("output", {})
        storage["temp"] = data_timed.get("temp", {})
        storage["meter"] = data_timed.get("meter", {})
        storage["monitoring"] = data_monitoring
        storage["manager"] = data_manager
    
    async def init(self):
        """Request a data initialisation from the Client. Collects "one-time" data."""
        try:
            await self.update()
            data_inverter = await self._client.get_data_onetime()
        except Exception as e:
            raise e

        self._storage["inverter"] = data_inverter

    # TODO one time data !! and an init()

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
    
            
if __name__ == "__main__":
    import asyncio
    import json

    # Tests
    async def _test():
        i = Inverter("192.168.200.110")
        await i.login("user@local", "password")
        await i.init()
        print(json.dumps(i._storage, indent=2, sort_keys=True))
        print(i.battery)

    asyncio.run(_test())