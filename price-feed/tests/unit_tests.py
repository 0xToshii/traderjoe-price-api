""" Unit tests covering rpc_wrapper
"""

import sys
sys.path.append("../")
import unittest

from utils.rpc_wrapper import tx_handler

rpc_endpoint = tx_handler("../abis/")
usdc_e = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
weth = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"

def perc_diff(val1,val2):
    return abs(val1-val2)/((val1+val2)/2)

class TestTxHandler(unittest.TestCase):

    def test_single_v1_tx_success(self):
        """ Testing that the price when swapping the base/quote tokens are similar within a threshold
            -this is using the USDC/ETH pool
        """
        rpc_out_1 = rpc_endpoint.handle_v1_requests([usdc_e],[weth])
        rpc_out_2 = rpc_endpoint.handle_v1_requests([weth],[usdc_e]) # swap order

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
        rpc_out_1 = rpc_endpoint.handle_v2_requests([usdc_e],[weth],[15])
        rpc_out_2 = rpc_endpoint.handle_v2_requests([weth],[usdc_e],[15]) # swap order

        self.assertEqual(rpc_out_1['status'],'SUCCESS')
        self.assertEqual(rpc_out_2['status'],'SUCCESS')

        prices_1 = rpc_out_1['output'][0]
        prices_2 = rpc_out_2['output'][0]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)

    
    def test_single_v2_1_tx_success(self):
        """ Testing that the price when swapping the base/quote tokens are similar within a threshold
            -this is using the USDC/ETH pool
        """
        rpc_out_1 = rpc_endpoint.handle_v2_1_requests([usdc_e],[weth],[15])
        rpc_out_2 = rpc_endpoint.handle_v2_1_requests([weth],[usdc_e],[15]) # swap order

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
        rpc_out_v1 = rpc_endpoint.handle_v1_requests([usdc_e],[weth])
        rpc_out_v2 = rpc_endpoint.handle_v2_requests([usdc_e],[weth],[15])
        rpc_out_v2_1 = rpc_endpoint.handle_v2_1_requests([usdc_e],[weth],[15])

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
        rpc_out = rpc_endpoint.handle_v1_requests([usdc_e,weth],[weth,usdc_e])

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
        rpc_out = rpc_endpoint.handle_v2_requests([usdc_e,weth],[weth,usdc_e],[15,15])

        self.assertEqual(rpc_out['status'],'SUCCESS')

        prices_1 = rpc_out['output'][0]
        prices_2 = rpc_out['output'][1]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)

    
    def test_multiple_v2_1_tx_success(self):
        """ Testing that multiple prices can be gathered at the same time
            -this is using the USDC/ETH pool
        """
        rpc_out = rpc_endpoint.handle_v2_1_requests([usdc_e,weth],[weth,usdc_e],[15,15])

        self.assertEqual(rpc_out['status'],'SUCCESS')

        prices_1 = rpc_out['output'][0]
        prices_2 = rpc_out['output'][1]
        self.assertTrue(perc_diff(prices_1**-1,prices_2)<0.01)

    
    def test_single_pool_doesnt_exist(self):
        """ Testing that if a pool doesn't exist an error is thrown
        """
        invalid_token="0x92aF49447D8a07e3bd95BD0d56f35241523fBab0" # doesn't exist

        rpc_out = rpc_endpoint.handle_v1_requests([usdc_e],[invalid_token])

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'At least one pair specified does not exist.')

    
    def test_two_pools_one_doesnt_exist(self):
        """ Testing that if even one pool of a multi-tx doesn't exist then error is thrown
        """
        invalid_token="0x92aF49447D8a07e3bd95BD0d56f35241523fBab0"  # doesn't exist

        rpc_out = rpc_endpoint.handle_v1_requests([usdc_e,usdc_e],[weth,invalid_token])

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'At least one pair specified does not exist.')

    
    def test_invalid_formatted_addresses_error(self):
        """ Test that error is thrown when a non-address is inputted
        """
        invalid_token='0x12345678'

        rpc_out = rpc_endpoint.handle_v1_requests([usdc_e],[invalid_token])

        self.assertEqual(rpc_out['status'],'ERROR')
        self.assertEqual(rpc_out['output'],'Asset addresses are incorrectly formatted.')

    
    def test_low_liquidity_pool(self):
        """ Test that the price for a low liquidity pool is returned at -1
            -it is possible this test might fail in the future if significantly more liquidity is added
        """
        link_address = "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4" # LINK token

        rpc_out = rpc_endpoint.handle_v2_requests([link_address],[weth],[10])

        self.assertEqual(rpc_out['status'],'SUCCESS')
        self.assertEqual(rpc_out['output'][0],-1)


    def test_low_liquidity_pool_multiple_pools(self):
        """ Test that the price for a low liquidity pool is returned at -1
            -also checks that the price of a valid pool is not also converted to -1
            -it is possible this test might fail in the future if significantly more liquidity is added
        """
        link_address = "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4" # LINK token

        rpc_out = rpc_endpoint.handle_v2_requests([link_address,usdc_e],[weth,weth],[10,15])

        self.assertEqual(rpc_out['status'],'SUCCESS')
        self.assertEqual(rpc_out['output'][0],-1)
        self.assertTrue(rpc_out['output'][1] != -1)



if __name__ == '__main__':

    unittest.main()
