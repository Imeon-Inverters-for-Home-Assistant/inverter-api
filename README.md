# Imeon Inverter Standalone API

[![GitHub Repository](https://img.shields.io/badge/-GitHub%20Repository-181717?logo=github)](https://github.com/Imeon-Inverters-for-Home-Assistant/inverter-api)
[![PyPI version](https://badge.fury.io/py/inverter-api.svg)](https://pypi.org/project/inverter-api/)
[![Website](https://img.shields.io/badge/-Imeon%20Energy-%2520?style=flat&label=Website&labelColor=grey&color=black)](https://imeon-energy.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-44cc11.svg)](https://www.apache.org/licenses/LICENSE-2.0)

A standalone API allowing communication with Imeon Energy inverters.
#

### Features
- uses HTTP POST/GET (auth + read-only)
- compatible with all models
- request rate limiter


### Planned
- changing inverter settings rom API calls

## Installation

You can install the package using pip:

```bash
pip install inverter_api
```
You can then simply use the package like this:
```python
import inverter_api
```

#
## Example
Here's a short example to authenticate then fetch hourly data from a given inverter:
```python
from inverter_api import Client
import asyncio
import json

# Display hourly data as a dict
async def dataset_test() -> dict:

    # Create a client for the address of the inverter
    c = Client("192.168.200.110")

    # Async authentification
    await c.login('user@local', 'password')

    # Fetch hourly data from the inverter
    data = await c.get_data_timed('hour')

    # Format the dict and print it
    print(json.dumps(data, indent=2, sort_keys=True))

asyncio.run(dataset_test())
```