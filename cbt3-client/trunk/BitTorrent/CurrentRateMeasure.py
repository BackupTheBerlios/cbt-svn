# Written by Bram Cohen
# see LICENSE.txt for license information

from time import time

class Measure:
    def __init__(self, max_rate_period, fudge = 1, total=0L):
        self.max_rate_period = max_rate_period
        self.ratesince = time() - fudge
        self.last = self.ratesince
        self.rate = 0.0
        self.total = total
        self.session_total = 0

    def update_rate(self, amount):
        self.total += amount
        self.session_total += amount
        t = time()
        self.rate = (self.rate * (self.last - self.ratesince) + 
            amount) / (t - self.ratesince)
        self.last = t
        if self.ratesince < t - self.max_rate_period:
            self.ratesince = t - self.max_rate_period

    def get_rate(self):
        self.update_rate(0)
        return self.rate

    def get_rate_noupdate(self):
        return self.rate

    def time_until_rate(self, newrate):
        if self.rate <= newrate:
            return 0
        t = time() - self.ratesince
        return ((self.rate * t) / newrate) - t

    def get_total(self):
        return self.total

    def get_session_total(self):
        return self.session_total