# Imeon Inverter Standalone API

[![GitHub Repository](https://img.shields.io/badge/-GitHub%20Repository-181717?logo=github)](https://github.com/Imeon-Inverters-for-Home-Assistant/inverter-api)
[![PyPI Package](https://img.shields.io/badge/-PyPI%20Package-%20?style=flat&logo=pypi&logoColor=white&color=%233775A9)](https://pypi.org/project/imeon-inverter-api/)
[![Website](https://img.shields.io/badge/-Imeon%20Energy-%2520?style=flat&label=Website&labelColor=grey&color=black)](https://imeon-energy.com/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-44cc11.svg)](https://www.apache.org/licenses/LICENSE-2.0)

A standalone API allowing communication with Imeon Energy inverters.

#

### Requirements

- Imeon OS One v1.8.1.0+ (release end of 2024).

### Features
- uses HTTP POST/GET (auth + read-only)
- compatible with all models
- request rate limiter


### Planned
- changing inverter settings from API calls

## Installation

You can install the package using pip:

```bash
pip install imeon_inverter_api
```
You can then simply use the package like this:
```python
import imeon_inverter_api
```


## Wiki

For documentation and some examples, please consult this project's **[wiki](https://github.com/Imeon-Inverters-for-Home-Assistant/inverter-api/wiki)**.
