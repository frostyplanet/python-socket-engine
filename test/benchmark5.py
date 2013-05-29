#!/usr/bin/env python
# coding:utf-8

from test_server import *
import _env
import lib.io_poll as io_poll

def main ():
    Log ("client", config=conf)
    Log ("server", config=conf)
    server = start_unblock_server (io_poll.EVPoll ())
    time.sleep (1)
    test_client ()

if __name__ == '__main__':
    main ()


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
