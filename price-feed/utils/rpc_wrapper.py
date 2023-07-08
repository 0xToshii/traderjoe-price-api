""" Wrapper for Web3py logic
    - all calls are wrapped into a Multicall function call
    - each API call (not checking price) involves 2 RPC requests: 
        1) first to determine whether the pairs exist
        2) then to get the info required to calculate the price of the pairs
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
            -this uses the base decimals of both tokens
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
            -this uses the base decimals of both tokens
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
        return {'status':'SUCCESS','output':all_prices}


    def handle_v1_requests(self,base_assets,quote_assets):
        """ Handles n-number of requests for getting prices of v1 pools
            -returns an error if any of the pools requested don't exist

        Args:
            base_assets (list): addresses of the base assets
            quote_assets (list): addresses of the quote assets

        Returns:
            List of amount of quote currency is required to get one unit of base currency
            -this uses the base decimals of both tokens
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
        return {'status':'SUCCESS','output':all_prices}

