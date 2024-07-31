from client import Client

class Inverter():

    def __init__(self, address) -> None:
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
            "manager": {}
        }
        return None
    
    async def login(self, username, password):
        if self.__auth_valid == False:
            try:
                await self._client.login(username, password)
                self.__auth_valid = True
            except Exception as e:
                raise Exception(f"Error while checking credentials: {e}")
            
    async def update(self, rate='minute'):
        pass

    # TODO login_required decorator here too, or something equivalent

    @property
    def battery(self): return self._storage.get("battery", None)

    @property
    def grid(self): return self._storage.get("grid", None)
    
    @property
    def pv(self): return self._storage.get("pv", None)
    
    @property
    def input(self): return self._storage.get("input", None)

    @property
    def output(self): return self._storage.get("output", None)
    
    @property
    def meter(self): return self._storage.get("meter", None)

    @property
    def temp(self): return self._storage.get("temp", None)
    
    @property
    def monitoring(self): return self._storage.get("monitoring", None)
    
    @property
    def manager(self): return self._storage.get("manager", None)
    
            
if __name__ == "__main__":

    # Tests
    def _test():
        i = Inverter("192.168.200.110")
        i.battery

    _test()