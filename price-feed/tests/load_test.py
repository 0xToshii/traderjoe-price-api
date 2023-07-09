""" Load testing - when API is deployed locally
    -performance at scale is based on available server hardware (e.g. number of workers)
    -i am testing this with a single worker, hence not testing this w/ multi-threaded reqs
    -rather just looking at the average return time (so not true load test)
"""

# uvicorn price_feed:app --host 0.0.0.0 --port 8443
# -p99: 0.811 seconds, -avg_time: 0.555 seconds

import requests
import time

def load_test_request():
    """ Makes V2 pool price request & returns status & time took
    """
    start = time.time()
    
    usdc_e = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
    weth = "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
    endpoint = "http://0.0.0.0:8443/v2/prices/{}/{}/{}".format(usdc_e,weth,15)
    ret = requests.get(endpoint)
    
    end = time.time()
    status = ret.status_code
    return (end-start,status)


def run_load_test():
    """ Run the load test and print results
    """ 
    all_status = 0
    all_took_time = []

    for i in range(100):
        metric = load_test_request()
        all_status += metric[1]==200
        all_took_time.append(metric[0])

    all_took_time.sort()

    print("-p99:",all_took_time[-2])
    print("-avg time:",sum(all_took_time)/len(all_took_time))
    print("-valid calls:",all_status/100)
    print("-------------------------------------")
    print(all_took_time)
    
    
if __name__=="__main__":
    run_load_test()
