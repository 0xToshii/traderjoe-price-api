""" Wrapper for Web3py logic
    - all calls are wrapped into a Multicall function call
    - each API call (not checking price) involves 2 RPC requests: 
        1) first to determine whether the pairs exist
        2) then to get the info required to calculate the price of the pairs
    - the API component for checking min USD liquidity involves:
        1) gather the prices of the core tokens (USDC,USDT,ETH)
            - for v1 pools, this is the only call required
        2) for v2/v2_1 pools loop through to get reserves for +/- 5 closest bins
            - this entails one extra call per requested base/quote pair
"""

import os
import json
import time
from web3 import Web3
from eth_abi import abi
from dotenv import load_dotenv
from web3.middleware import geth_poa_middleware
from web3.middleware import validation
validation.METHODS_TO_VALIDATE = [] # removes the chainId validation, to reduce no. calls


class tx_handler:
    """ Logic for interacting with RPC endpoint
    """
    def __init__(self,abi_path):
        """ Init
        """
        self.gather_and_instantiate_contracts(abi_path)
        self.address_zero = '0x0000000000000000000000000000000000000000'

        self.chainlink_info = { # USDC and USDC.e use the same chainlink address, both used across pairs
            '0xaf88d065e77c8cC2239327C5EDb3A432268e5831':{'token_precision':1e6,'name':'USDC',
                                                          'chainlink_address':'0x50834F3163758fcC1Df9973b6e91f0F0F0434aD3'},
            '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8':{'token_precision':1e6,'name':'USDC.e',
                                                          'chainlink_address':'0x50834F3163758fcC1Df9973b6e91f0F0F0434aD3'},
            '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9':{'token_precision':1e6,'name':'USDT',
                                                          'chainlink_address':'0x3f3f5dF88dC9F13eac63DF89EC16ef6e7E25DdE7'},
            '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1':{'token_precision':1e18,'name':'wETH',
                                                          'chainlink_address':'0x639Fe6ab55C921f74e7fac1ee960C0B6293ba612'},
        }


    def gather_and_instantiate_contracts(self,abi_path):
        """ Gathers all the contract abi(s) and instantiates the factory + multicall contracts
        """
        # instantiating the connection to RPC endpoint
        load_dotenv()
        rpc = os.getenv('RPC')
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        self.w3.middleware_onion.inject(geth_poa_middleware,layer=0)
        assert(self.w3.isConnected() == True)

        # instantiating factory contracts & multicall
        joe_v2_factory_abi = json.load(open(abi_path+"JoeV2Factory.json"))
        self.joe_v2_factory = self.w3.eth.contract(address=os.getenv('FACTORY_V2'),abi=joe_v2_factory_abi)
        self.joe_v2_1_factory = self.w3.eth.contract(address=os.getenv('FACTORY_V2_1'),abi=joe_v2_factory_abi)

        joe_v1_factory_abi = json.load(open(abi_path+"JoeV1Factory.json"))
        self.joe_v1_factory = self.w3.eth.contract(address=os.getenv('FACTORY_V1'),abi=joe_v1_factory_abi)

        multicall_abi = json.load(open(abi_path+"Multicall.json"))
        self.multicall = self.w3.eth.contract(address=os.getenv('MULTICALL'),abi=multicall_abi)

        # pair addresses are used to encode abi
        lb_pair_v2_abi = json.load(open(abi_path+"LBPairV2.json"))
        self.lb_pair_v2 = self.w3.eth.contract(abi=lb_pair_v2_abi)

        lb_pair_v2_1_abi = json.load(open(abi_path+"LBPairV2_1.json"))
        self.lb_pair_v2_1 = self.w3.eth.contract(abi=lb_pair_v2_1_abi)

        joe_pair_abi = json.load(open(abi_path+"JoePair.json"))
        self.joe_pair = self.w3.eth.contract(abi=joe_pair_abi)

        chainlink_abi = json.load(open(abi_path+"Chainlink.json"))
        self.chainlink_feed = self.w3.eth.contract(abi=chainlink_abi)


    def attempt_multicall_request(self,multicall_inputs):
        """ Calls the multicall contract with inputs, attempts call 2 more times if failure
        """
        try:
            return self.multicall.functions.aggregate(multicall_inputs).call()
        except:
            time.sleep(1)
            try:
                return self.multicall.functions.aggregate(multicall_inputs).call()
            except:
                time.sleep(3)
                return self.multicall.functions.aggregate(multicall_inputs).call()


    def check_valid_v2_inputs(self,base_assets,quote_assets,bin_steps):
        """ Checks whether user inputs are valid for the call they are attempting for v2 & v2_1 pools
            -return error string if there is an error, else empty string
        """
        if len(base_assets) != len(quote_assets) or len(quote_assets) != len(bin_steps): # check equal len
            return "Length of base_assets, quote_assets, and bin_steps needs to be equal."
        
        return self.check_valid_inputs(base_assets,quote_assets)


    def check_valid_v1_inputs(self,base_assets,quote_assets):
        """ Checks whether user inputs are valid for the call they are attempting for v1 pools
        """
        return self.check_valid_inputs(base_assets,quote_assets)


    def check_valid_inputs(self,base_assets,quote_assets):
        """ Generic validation checks for both v1 and v2/v2_1 pools
        """
        for assets in [base_assets,quote_assets]: # check address formatting
            for asset in assets:
                if type(asset)!=str or len(asset)!=42 or asset==self.address_zero:
                    return "Asset addresses are incorrectly formatted."

        for assets in [base_assets,quote_assets]: # ensure addresses are checksum
            for i in range(len(assets)):
                assets[i] = Web3.toChecksumAddress(assets[i])

        return ""


    def calculate_lb_pool_price(self,active_id,bin_step):
        """ Calculates and returns price based on active bin id and bin step
            -this does not account for whether the price needs to be inverted based on base/quote assets
        """
        return (1 + bin_step / 10_000) ** (active_id - 8388608)


    def return_v2_and_v2_1_prices(self,base_assets,quote_assets,bin_steps,all_pair_active_ids):
        """ Returns the price for v2 and v2_1 pools, based on active bin id & token ordering
            -by default the 'smaller' address is used as the denominator for pool price calc.
            -therefore simply need to check if the smaller address is the base asset (done)
            -on the other hand, if base asset address is 'larger', then need to invert price
        """
        prices = []
        for i in range(len(base_assets)):
            price = self.calculate_lb_pool_price(all_pair_active_ids[i],bin_steps[i])
            if base_assets[i].lower() > quote_assets[i].lower(): # determine if price needs to be swapped
                price = price ** -1
            prices.append(price)

        return prices


    def return_v1_prices(self,base_assets,quote_assets,all_pair_reserves):
        """ Returns the price for v1 pools, simply the ratio of the token reserves
        """
        prices = []
        for i in range(len(base_assets)):
            if base_assets[i].lower() < quote_assets[i].lower():
                prices.append(all_pair_reserves[i][1]/all_pair_reserves[i][0])
            else:
                prices.append(all_pair_reserves[i][0]/all_pair_reserves[i][1])

        return prices


    def gather_v1_pair_addresses(self,base_assets,quote_assets):
        """ Logic for gathering the pair addresses for v1 pools
        """
        # gather all of the addresses of the pairs specified by the user
        multicall_input = []
        for i in range(len(base_assets)):
            abi_encoding = self.joe_v1_factory.encodeABI(fn_name="getPair",
                                                         args=[base_assets[i],quote_assets[i]])
            multicall_input.append([self.joe_v1_factory.address,abi_encoding])
        
        multicall_output = self.attempt_multicall_request(multicall_input)

        # determine whether all pairs are valid by getting pair address
        all_pair_addresses = [] # indiv pairs requested prices for
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['address'],multicall_output[1][i])
            decoded_address = decoding[0]
            if decoded_address == self.address_zero: # check if requested pair exists
                return {'status':'ERROR','output':'At least one pair specified does not exist.'}
            all_pair_addresses.append(Web3.toChecksumAddress(decoded_address)) # not checksum by default

        return all_pair_addresses


    def gather_v2_and_v2_1_pair_addresses(self,base_assets,quote_assets,bin_steps,factory_address):
        """ Logic for gathering pair addresses, is the same for both v2 and v2_1
        """
        # gather all of the addresses of the pairs specified by the user
        multicall_input = []
        for i in range(len(base_assets)):
            abi_encoding = self.joe_v2_factory.encodeABI(fn_name="getLBPairInformation",
                                                         args=[base_assets[i],quote_assets[i],bin_steps[i]])
            multicall_input.append([factory_address,abi_encoding])
        
        multicall_output = self.attempt_multicall_request(multicall_input)

        # determine whether all pairs are valid by getting pair address
        all_pair_addresses = [] # indiv pairs requested prices for
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['uint16','address','bool','bool'],multicall_output[1][i])
            decoded_address = decoding[1]
            if decoded_address == self.address_zero: # check if requested pair exists
                return {'status':'ERROR','output':'At least one pair specified does not exist.'}
            all_pair_addresses.append(Web3.toChecksumAddress(decoded_address)) # not checksum by default

        return all_pair_addresses


    def handle_v2_requests(self,base_assets,quote_assets,bin_steps):
        """ Handles n-number of requests for getting prices of v2 pools
            -returns an error if any of the pools requested don't exist

        Args:
            base_assets (list): addresses of the base assets
            quote_assets (list): addresses of the quote assets
            bin_steps (list): sizes of the bins for the pairs

        Returns:
            List of amount of quote currency is required to get one unit of base currency
            -returns -1 for the price if pool doesn't have enough liquidity in local bins
        """
        validity = self.check_valid_v2_inputs(base_assets,quote_assets,bin_steps) # check params
        if validity != "":
            return {'status':'ERROR','output':validity}

        # gather all pair addresses based on user input
        factory_address = self.joe_v2_factory.address
        all_pair_addresses = self.gather_v2_and_v2_1_pair_addresses(base_assets,quote_assets,
                                                                    bin_steps,factory_address)
        if type(all_pair_addresses)==dict: # error occured
            return all_pair_addresses

        # gather the price info from the individual pairs
        reserves_func_call = self.lb_pair_v2.encodeABI(fn_name="getReservesAndId",args=[])
        
        multicall_input = []
        for pair_address in all_pair_addresses:
            multicall_input.append([pair_address,reserves_func_call])

        multicall_output = self.attempt_multicall_request(multicall_input)

        # decoding pair info from multicall
        all_pair_active_ids = [] # activeId specifies the current bin, which determines the current price
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['uint256','uint256','uint256'],multicall_output[1][i])
            decoded_active_id = decoding[2]
            all_pair_active_ids.append(decoded_active_id)

        # gathering the prices requested by user
        all_prices = self.return_v2_and_v2_1_prices(base_assets,quote_assets,bin_steps,all_pair_active_ids)

        # check if pool bins have enough liquidity, convert price to -1 if they don't
        all_prices = self.check_v2_and_v2_1_liquidity(base_assets,quote_assets,all_prices,
                                                      all_pair_active_ids,all_pair_addresses)

        return {'status':'SUCCESS','output':all_prices}


    def handle_v2_1_requests(self,base_assets,quote_assets,bin_steps):
        """ Handles n-number of requests for getting prices of v2_1 pools
            -returns an error if any of the pools requested don't exist

        Args:
            base_assets (list): addresses of the base assets
            quote_assets (list): addresses of the quote assets
            bin_steps (list): sizes of the bins for the pairs

        Returns:
            List of amount of quote currency is required to get one unit of base currency
            -returns -1 for the price if pool doesn't have enough liquidity in local bins
        """
        validity = self.check_valid_v2_inputs(base_assets,quote_assets,bin_steps) # check params
        if validity != "":
            return {'status':'ERROR','output':validity}

        # gather all pair addresses based on user input
        factory_address = self.joe_v2_1_factory.address
        all_pair_addresses = self.gather_v2_and_v2_1_pair_addresses(base_assets,quote_assets,
                                                                    bin_steps,factory_address)
        if type(all_pair_addresses)==dict: # error occured
            return all_pair_addresses

        # gather the price info from the individual pairs
        active_id_func_call = self.lb_pair_v2_1.encodeABI(fn_name="getActiveId",args=[])
        
        multicall_input = []
        for pair_address in all_pair_addresses:
            multicall_input.append([pair_address,active_id_func_call])

        multicall_output = self.attempt_multicall_request(multicall_input)

        # decoding pair info from multicall
        all_pair_active_ids = [] # activeId specifies the current bin, which determines the current price
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['uint24'],multicall_output[1][i])
            decoded_active_id = decoding[0]
            all_pair_active_ids.append(decoded_active_id)

        # gathering the prices requested by user
        all_prices = self.return_v2_and_v2_1_prices(base_assets,quote_assets,bin_steps,all_pair_active_ids)

        # check if pool bins have enough liquidity, convert price to -1 if they don't
        all_prices = self.check_v2_and_v2_1_liquidity(base_assets,quote_assets,all_prices,
                                                      all_pair_active_ids,all_pair_addresses)

        return {'status':'SUCCESS','output':all_prices}


    def check_v2_and_v2_1_liquidity(
            self,base_assets,quote_assets,all_prices,all_pair_active_ids,
            all_pair_addresses,min_liquidity_per_bin_usd=10):
        """ Determines whether there is enough liquidity in v2 & v2_1 pairs
            -skips over pairs which are not paired with (USDC,USDT,ETH)
            -results in price of -1 being returned if pool does not have enough liquidity
            -this is based on checking the USD value of the 5 bins above and below the current active bin
        """
        core_prices = self.gather_core_usd_prices()
        surrounding_bins = [-5,-4,-3,-2,-1,1,2,3,4,5] # offset of bins which will be checked

        for i in range(len(base_assets)):
            # first checks whether this pair should be skipped
            if base_assets[i] not in core_prices and quote_assets[i] not in core_prices:
                ##print('could not price pool')
                continue

            # for each token, first gather the reserves in the +/- 5 bins around the current active bin
            pool_surrounding_bins = [all_pair_active_ids[i]+offset for offset in surrounding_bins]

            multicall_input = []
            for local_bin in pool_surrounding_bins:
                bin_reserves_func_call = self.lb_pair_v2.encodeABI(fn_name="getBin",args=[local_bin]) # same for v2/v2_1
                multicall_input.append([all_pair_addresses[i],bin_reserves_func_call])

            multicall_output = self.attempt_multicall_request(multicall_input)

            all_bin_reserves = []
            for j in range(len(multicall_output[1])):
                decoding = abi.decode(['uint256','uint256'],multicall_output[1][j])
                all_bin_reserves.append(decoding) # reserveX,reserveY; recall that reserveX is for the 'smaller' of the two tokens

            bins_have_enough_liq = self.convert_bin_reserves_to_price(base_assets[i],quote_assets[i],all_prices[i],
                                                                      all_bin_reserves,core_prices,
                                                                      min_liquidity_per_bin_usd)
            if bins_have_enough_liq == False:
                all_prices[i]=-1

        return all_prices


    def convert_bin_reserves_to_price(
        self,base_asset,quote_asset,price,all_bin_reserves,
        core_prices,min_liquidity_per_bin_usd):
        """ Determines the USD price for each of the bins based on their reserves
            -returns True/False for whether all of the local bins have >= min_liquidity_per_bin_usd
        """
        for reserves in all_bin_reserves:
            reserve_x,reserve_y = reserves
            #assert(reserve_x==0 or reserve_y==0) # invariant

            if base_asset.lower() < quote_asset.lower(): # base token is reserve_x, quote token is reserve_y
                base_amount = reserve_x
                quote_amount = reserve_y
            else:
                base_amount = reserve_y
                quote_amount = reserve_x

            # remember that the default price is stored in (quote/base)

            if base_asset in core_prices: # we have USD value for the base_asset
                # calculate the value of reserve_x
                bin_value_usd = base_amount/core_prices[base_asset]['token_precision']*core_prices[base_asset]['price']
                # calculate the value of reserve_y
                # -price is currently quote/base, so need to swap to base/quote
                # -final eq: quote_amount * (base/quote) / (base precision) * (base price)
                bin_value_usd += quote_amount*(price ** -1)/core_prices[base_asset]['token_precision']*core_prices[base_asset]['price']

            else: # we have USD value of quote asset
                bin_value_usd = quote_amount/core_prices[quote_asset]['token_precision']*core_prices[quote_asset]['price']
                # calcualte the value of reserve_x
                # -price is currently quote/base, which is what we need
                # -final eq: base_amount * (quote/base) / (quote precision) * (quote price)
                bin_value_usd += base_amount*(price)/core_prices[quote_asset]['token_precision']*core_prices[quote_asset]['price']

            ##print("-bin value:",bin_value_usd)
            if bin_value_usd < min_liquidity_per_bin_usd: # at least on bin didn't have enough liquidity
                return False

        return True


    def handle_v1_requests(self,base_assets,quote_assets):
        """ Handles n-number of requests for getting prices of v1 pools
            -returns an error if any of the pools requested don't exist

        Args:
            base_assets (list): addresses of the base assets
            quote_assets (list): addresses of the quote assets

        Returns:
            List of amount of quote currency is required to get one unit of base currency
            -returns -1 for the price if pool doesn't have enough liquidity
        """
        validity = self.check_valid_v1_inputs(base_assets,quote_assets) # check params
        if validity != "":
            return {'status':'ERROR','output':validity}

        # gather all pair addresses based on user input
        all_pair_addresses = self.gather_v1_pair_addresses(base_assets,quote_assets)
        if type(all_pair_addresses)==dict: # error occured
            return all_pair_addresses

        # gather the reserves info from the individual pairs
        get_reserves_func_call = self.joe_pair.encodeABI(fn_name="getReserves",args=[])
        
        multicall_input = []
        for pair_address in all_pair_addresses:
            multicall_input.append([pair_address,get_reserves_func_call])

        multicall_output = self.attempt_multicall_request(multicall_input)

        # decoding pair info from multicall
        all_pair_reserves = [] # reserves of (tokenX,tokenY)
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['uint112','uint112','uint32'],multicall_output[1][i])
            decoded_token_x_reserves,decoded_token_y_reserves,_ = decoding
            all_pair_reserves.append((decoded_token_x_reserves,decoded_token_y_reserves))

        # gathering the prices requested by user
        all_prices = self.return_v1_prices(base_assets,quote_assets,all_pair_reserves)

        # check if pools have enough liquidity, convert price to -1 if they don't
        all_prices = self.check_v1_liquidity(base_assets,quote_assets,all_pair_reserves,all_prices)

        return {'status':'SUCCESS','output':all_prices}


    def check_v1_liquidity(self,base_assets,quote_assets,all_pair_reserves,all_prices,min_liquidity_usd=100):
        """ Determines whether there is enough liquidity in v1 pairs 
            -skips over pairs which are not paired with (USDC,USDT,ETH)
            -results in price of -1 being returned if pool does not have enough liquidity
            -v1 pools don't require the price between assets, b/c the USD value of both tokens are equal
        """
        core_prices = self.gather_core_usd_prices()

        for i in range(len(base_assets)):
            if base_assets[i].lower() < quote_assets[i].lower(): # base asset is tokenX, quote asset is tokenY
                base_amount = all_pair_reserves[i][0]
                quote_amount = all_pair_reserves[i][1]
            else:
                base_amount = all_pair_reserves[i][1]
                quote_amount = all_pair_reserves[i][0]

            if base_assets[i] in core_prices: # we have USD price for base asset
                total_liquidity = (base_amount/core_prices[base_assets[i]]['token_precision'])*2

                total_price = total_liquidity*core_prices[base_assets[i]]['price']
                if total_price < min_liquidity_usd: # not enough liquidity
                    all_prices[i]=-1

            elif quote_assets[i] in core_prices: # we have USD price for quote asset
                total_liquidity = (quote_amount/core_prices[quote_assets[i]]['token_precision'])*2

                total_price = total_liquidity*core_prices[quote_assets[i]]['price']
                if total_price < min_liquidity_usd: # not enough liquidity
                    all_prices[i]=-1

            else: # unable to price this pool
                ##print('could not price pool')
                continue

        return all_prices


    def gather_core_usd_prices(self,precision=1e8):
        """ Gathers the USD prices for main price comparison tokens (USDC,USDT,ETH)
            -done by querying the USD prices from chainlink (which have 1e8 precision)
        """
        get_latest_answer_call = self.chainlink_feed.encodeABI(fn_name="latestAnswer",args=[])

        multicall_input = []
        for token in self.chainlink_info:
            multicall_input.append([self.chainlink_info[token]['chainlink_address'],get_latest_answer_call])

        multicall_output = self.attempt_multicall_request(multicall_input)

        # decoding prices
        all_token_prices = []
        for i in range(len(multicall_output[1])):
            decoding = abi.decode(['int256'],multicall_output[1][i])
            price = decoding[0]/precision # remove precision, convert to float
            all_token_prices.append(price)

        prices = {}
        for i,token in enumerate(self.chainlink_info):
            prices[token] = {'price':all_token_prices[i],'token_precision':self.chainlink_info[token]['token_precision']}

        return prices

