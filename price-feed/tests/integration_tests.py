""" Integration tests for the FastAPI logic
"""

import sys
sys.path.append("../")
import json
import unittest
from fastapi.testclient import TestClient

from price_feed import app

client = TestClient(app)

usdc_e = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
weth = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"

def perc_diff(val1,val2):
    return abs(val1-val2)/((val1+val2)/2)

class TestTxHandler(unittest.TestCase):

    def test_endpoint_is_up(self):
        """ Simply checks that the endpoint is working
        """
        response = client.get("/")
    
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),"yes")


    def test_invalid_endpoint_used(self):
        """ Testing that 404 is returned when trying to used an invalid endpoint
        """
        resp = client.get("/random")
        self.assertEqual(resp.status_code,404)


    def test_single_v1_tx_success(self):
        """ Testing that the price when swapping the base/quote tokens are similar within a threshold
            -this is using the USDC/ETH pool
        """
        resp_1 = client.get("/v1/prices/{}/{}".format(usdc_e,weth))
        resp_2 = client.get("/v1/prices/{}/{}".format(weth,usdc_e)) # swap order

        self.assertEqual(resp_1.status_code,200)
        self.assertEqual(resp_2.status_code,200)

        rpc_out_1 = resp_1.json()
        rpc_out_2 = resp_2.json()

        self.assertEqual(rpc_out_1['status'],'SUCCESS')
        self.assertEqual(rpc_out_2['status'],'SUCCESS')

        prices_1 = rpc_out_1['output'][0]
        prices_2 = rpc_out_2['output'][0]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)


    def test_single_v2_tx_success(self):
        """ Testing that the price when swapping the base/quote tokens are similar within a threshold
            -this is using the USDC/ETH pool
            -it is possible this fails depending on the future pool dist as the liquidity 
            -is fairly close to hitting the lower limit (as of when this was created)
        """
        resp_1 = client.get("/v2/prices/{}/{}/{}".format(usdc_e,weth,15))
        resp_2 = client.get("/v2/prices/{}/{}/{}".format(weth,usdc_e,15)) # swap order

        self.assertEqual(resp_1.status_code,200)
        self.assertEqual(resp_2.status_code,200)

        rpc_out_1 = resp_1.json()
        rpc_out_2 = resp_2.json()

        self.assertEqual(rpc_out_1['status'],'SUCCESS')
        self.assertEqual(rpc_out_2['status'],'SUCCESS')

        prices_1 = rpc_out_1['output'][0]
        prices_2 = rpc_out_2['output'][0]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)

    
    def test_single_v2_1_tx_success(self):
        """ Testing that the price when swapping the base/quote tokens are similar within a threshold
            -this is using the USDC/ETH pool
        """
        resp_1 = client.get("/v2_1/prices/{}/{}/{}".format(usdc_e,weth,15))
        resp_2 = client.get("/v2_1/prices/{}/{}/{}".format(weth,usdc_e,15)) # swap order

        self.assertEqual(resp_1.status_code,200)
        self.assertEqual(resp_2.status_code,200)

        rpc_out_1 = resp_1.json()
        rpc_out_2 = resp_2.json()

        self.assertEqual(rpc_out_1['status'],'SUCCESS')
        self.assertEqual(rpc_out_2['status'],'SUCCESS')

        prices_1 = rpc_out_1['output'][0]
        prices_2 = rpc_out_2['output'][0]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)


    def test_single_tx_across_all_pools_equal(self):
        """ Testing that the price returned across all pools are close within a threshold
            -it is possible this won't hold true if there is a huge swap that isn't arbed yet
            -however that likelihood is low, and in general all pools should have similar prices
        """
        resp_v1 = client.get("/v1/prices/{}/{}".format(usdc_e,weth))
        resp_v2 = client.get("/v2/prices/{}/{}/{}".format(usdc_e,weth,15))
        resp_v2_1 = client.get("/v2_1/prices/{}/{}/{}".format(usdc_e,weth,15))

        self.assertEqual(resp_v1.status_code,200)
        self.assertEqual(resp_v2.status_code,200)
        self.assertEqual(resp_v2_1.status_code,200)

        rpc_out_v1 = resp_v1.json()
        rpc_out_v2 = resp_v2.json()
        rpc_out_v2_1 = resp_v2_1.json()

        self.assertEqual(rpc_out_v1['status'],'SUCCESS')
        self.assertEqual(rpc_out_v2['status'],'SUCCESS')
        self.assertEqual(rpc_out_v2_1['status'],'SUCCESS')

        price_diff_perc_a = perc_diff(rpc_out_v1['output'][0],rpc_out_v2['output'][0])
        price_diff_perc_b = perc_diff(rpc_out_v2['output'][0],rpc_out_v2_1['output'][0])

        self.assertTrue(price_diff_perc_a<0.01)
        self.assertTrue(price_diff_perc_b<0.01)


    def test_multiple_v1_tx_success(self):
        """ Testing that multiple prices can be gathered at the same time
            -this is using the USDC/ETH pool
        """
        data = json.dumps({'base_assets':[usdc_e,weth],'quote_assets':[weth,usdc_e]})
        resp = client.post("/v1/batch-prices",data=data)

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'SUCCESS')

        prices_1 = rpc_out['output'][0]
        prices_2 = rpc_out['output'][1]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)


    def test_multiple_v2_tx_success(self):
        """ Testing that multiple prices can be gathered at the same time
            -this is using the USDC/ETH pool
            -it is possible this fails depending on the future pool dist as the liquidity 
            -is fairly close to hitting the lower limit (as of when this was created)
        """
        data = json.dumps({'base_assets':[usdc_e,weth],'quote_assets':[weth,usdc_e],'bin_steps':[15,15]})
        resp = client.post("/v2/batch-prices",data=data)

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'SUCCESS')

        prices_1 = rpc_out['output'][0]
        prices_2 = rpc_out['output'][1]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)


    def test_multiple_v2_1_tx_success(self):
        """ Testing that multiple prices can be gathered at the same time
            -this is using the USDC/ETH pool
        """
        data = json.dumps({'base_assets':[usdc_e,weth],'quote_assets':[weth,usdc_e],'bin_steps':[15,15]})
        resp = client.post("/v2_1/batch-prices",data=data)

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'SUCCESS')

        prices_1 = rpc_out['output'][0]
        prices_2 = rpc_out['output'][1]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)


    def test_single_pool_doesnt_exist(self):
        """ Testing that if a pool doesn't exist an error is thrown
        """
        invalid_token="0x92aF49447D8a07e3bd95BD0d56f35241523fBab0" # doesn't exist

        resp = client.get("/v1/prices/{}/{}".format(usdc_e,invalid_token))

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'At least one pair specified does not exist.')


    def test_two_pools_one_doesnt_exist(self):
        """ Testing that if even one pool of a multi-tx doesn't exist then error is thrown
        """
        invalid_token="0x92aF49447D8a07e3bd95BD0d56f35241523fBab0"  # doesn't exist

        data = json.dumps({'base_assets':[usdc_e,usdc_e],'quote_assets':[weth,invalid_token]})

        resp = client.post("/v1/batch-prices",data=data)

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'At least one pair specified does not exist.')


    def test_invalid_formatted_addresses_error(self):
        """ Test that error is thrown when a non-address is inputted
        """
        invalid_token='0x12345678'

        resp = client.get("/v1/prices/{}/{}".format(usdc_e,invalid_token))

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'Asset addresses are incorrectly formatted.')


    def test_low_liquidity_pool(self):
        """ Test that the price for a low liquidity pool is returned at -1
            -it is possible this test might fail in the future if significantly more liquidity is added
        """
        link_address = "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4" # LINK token

        resp = client.get("/v2/prices/{}/{}/{}".format(link_address,weth,10))

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'SUCCESS')
        self.assertEqual(rpc_out['output'][0],-1)


    def test_low_liquidity_pool_multiple_pools(self):
        """ Test that the price for a low liquidity pool is returned at -1
            -also checks that the price of a valid pool is not also converted to -1
            -it is possible this test might fail in the future if significantly more liquidity is added
        """
        link_address = "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4" # LINK token

        data = json.dumps({'base_assets':[link_address,usdc_e],'quote_assets':[weth,weth],'bin_steps':[10,15]})
        resp = client.post("/v2/batch-prices",data=data)

        self.assertEqual(resp.status_code,200)

        rpc_out = resp.json()

        self.assertEqual(rpc_out['status'],'SUCCESS')
        self.assertEqual(rpc_out['output'][0],-1)
        self.assertTrue(rpc_out['output'][1] != -1)



if __name__ == '__main__':

    unittest.main()
