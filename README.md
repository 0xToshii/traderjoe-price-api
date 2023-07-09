# Trader Joe Price Feed API

## Description

This Trader Joe Price Feed API is intended to be used to get the prices of v1, v2, and v2_1 pools on Arbitrum. It is written in python and primarily utilizes the Web3py and FastAPI packages. Prices are only returned for pools in which (for v1) there is more than 100 USD in liquidity, or (for v2 and v2_1) for each of the +/- 5 closest bins to the active bin, there is at least 10 USD in liquidity. If these conditions are not met, then the price returned will be -1. If any of the pools requested do not exist, then the API will return an error. To save on RPC calls, most functionality is wrapped using Multicall. USD prices for assets are gathered using Chainlink price feeds.

## Usage

1. Install `requirements.txt` using a virtual environment.
2. In `.env` define the following: 
    1. `RPC`: RPC endpoint for Arbitrum, 
    2. `FACTORY_V1`: Address of the TraderJoe V1 factory (0xaE4EC9901c3076D0DdBe76A520F9E90a6227aCB7)
    3. `FACTORY_V2`: Address of the TraderJoe V2 factory (0x1886D09C9Ade0c5DB822D85D21678Db67B6c2982)
    4. `FACTORY_V2_1`: Address of the TraderJoe V2_1 factory (0x8e42f2F4101563bF679975178e880FD87d3eFd4e)
    5. `MULTICALL`: Address of the Multicall contract (0x842eC2c7D803033Edf55E478F461FC547Bc54EB2)
3. Start the API by running the following: `uvicorn price_feed:app --host 0.0.0.0 --port 8443`

## API Definition

Supports the following calls:
- V1 - GET /v1/prices/{base asset}/{quote asset}
- V2 - GET /v2/prices/{base asset}/{quote asset}/{bin step}
- V2.1 - GET /v2_1/prices/{base asset}/{quote asset}/{bin step}
- V1 - POST /v1/batch-prices
- V2 - POST /v2/batch-prices
- V2.1 - POST /v2_1/batch-prices

Example python code for calling the endpoint:

```python
import requests
import json
USDC_e = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8' 
wETH = '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1'

# single pair GET v1 request
endpoint = "http://0.0.0.0:8443/v1/prices/{}/{}".format(USDC_e,wETH)
requests.get(endpoint)

# multi-pair POST v1 request
endpoint = "http://0.0.0.0:8443/v1/batch-prices"
data = json.dumps({'base_assets':[USDC_e,wETH],'quote_assets':[wETH,USDC]})
requests.post(endpoint,data=data)
```

## Performance
Performance is based on GET requests for v2 pools:
- p99 response time: 0.811 seconds
- Average response time: 0.555 seconds

