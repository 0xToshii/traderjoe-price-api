""" Core FastAPI logic
"""

from fastapi import FastAPI,Request
from pydantic import BaseModel
from typing import List

from utils.rpc_wrapper import tx_handler
from utils.rate_limiter import rate_limiter

tx_handler = tx_handler("./abis/")
rate_limiter = rate_limiter(100)


class DataV1(BaseModel):
    base_assets: List[str]
    quote_assets: List[str]

class DataV2(BaseModel):
    base_assets: List[str]
    quote_assets: List[str]
    bin_steps: List[int]

app = FastAPI()


@app.get("/")
async def check_uptime():
    """ Used to determine if endpoint is up
    """
    return "yes"


@app.get("/v1/prices/{base_asset}/{quote_asset}")
async def get_single_v1_price(base_asset:str,quote_asset:str):
    """ Gets a single price per v1 pool, as defined by base_asset,quote_asset
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v1_requests([base_asset],[quote_asset])
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


@app.get("/v2/prices/{base_asset}/{quote_asset}/{bin_step}")
async def get_single_v2_price(base_asset:str,quote_asset:str,bin_step:int):
    """ Gets a single price per v2 pool, as defined by base_asset,quote_asset,bin_step
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v2_requests([base_asset],[quote_asset],[bin_step])
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


@app.get("/v2_1/prices/{base_asset}/{quote_asset}/{bin_step}")
async def get_single_v2_1_price(base_asset:str,quote_asset:str,bin_step:int):
    """ Gets a single price per v2_1 pool, as defined by base_asset,quote_asset,bin_step
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v2_1_requests([base_asset],[quote_asset],[bin_step])
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


@app.post("/v1/batch-prices")
async def get_batch_v1_prices(data:DataV1):
    """ Gets batch of prices for v1 pools, as defined by base_assets,quote_assets
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v1_requests(data.base_assets,data.quote_assets)
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


@app.post("/v2/batch-prices")
async def get_batch_v2_prices(data:DataV2):
    """ Gets batch of prices for v2 pools, as defined by base_assets,quote_assets,bin_steps
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v2_requests(data.base_assets,data.quote_assets,data.bin_steps)
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


@app.post("/v2_1/batch-prices")
async def get_batch_v2_1_prices(data:DataV2):
    """ Gets batch of prices for v2_1 pools, as defined by base_assets,quote_assets,bin_steps
    """
    try:
        limit_str = rate_limiter.attempt_call()
        if limit_str != "":
            return {'status':'ERROR','output':limit_str}

        return tx_handler.handle_v2_1_requests(data.base_assets,data.quote_assets,data.bin_steps)
    except Exception as e: # will catch e.g. RPC errors
        return {'status':'ERROR','output':str(e)}


