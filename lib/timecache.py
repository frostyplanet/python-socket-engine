#!/usr/bin/env python

from select import select
import threading
import time

class TimeCache (object):

    cur_time = None 
    precise = None
    _th = None
    running = False

    def __init__ (self, precise=1.0):
        assert precise > 0.0
        self.precise = precise
        self.cur_time = time.time ()
        
    def time (self):
        return self.cur_time

    def start (self):
        if self.running:
            return
        self.running = True
        _th = threading.Thread (target=self._update)
        _th.setDaemon (1)
        _th.start ()
        self._th = _th
    
    def stop (self):
        if not self.running:
            return
        self.running = False
        assert self._th
        self._th.join ()
        self._th = None

    def _update (self):
        while self.running:
            self.cur_time = time.time ()
            select ([], [], [], self.precise)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
