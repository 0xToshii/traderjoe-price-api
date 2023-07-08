""" Logic for implementing global rate limiting
    -uses thread-safe PriorityQueue to keep track of traffic
"""

import queue
import pytz
from datetime import datetime,timedelta


class rate_limiter:
    def __init__(self,max_calls_per_min):
        """ Init
        """
        self.max_calls_per_min = max_calls_per_min # rate limit
        self.queue = queue.PriorityQueue() # thread-safe
        self.timezone = pytz.UTC


    def attempt_call(self):
        """ Has logic to determine where to fail call based on rate limit
            -returns error string on error, or empty string on success
        """
        now = self.timezone.localize(datetime.now())
        if self.queue.qsize() < self.max_calls_per_min: # accept call
            self.queue.put(now)
            return ""
        else: # determine whether oldest call is past a min.
            oldest_timestamp = self.queue.get()
            now_minus_min = now-timedelta(minutes=1)
            if now_minus_min >= oldest_timestamp: # oldest timestamp is over a min old, accept call 
                self.queue.put(now)
                return ""
            else:
                self.queue.put(oldest_timestamp) # stick oldest timestamp back in queue
                return "Rate limit reached."

