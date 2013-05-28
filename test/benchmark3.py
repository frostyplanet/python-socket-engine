#!/usr/bin/env python
# coding:utf-8

from test_server import *

def main ():
    Log ("client", config=conf)
    Log ("server", config=conf)
    server = start_unblock_server ()
    time.sleep (1)
    test_client_unblock ()

if __name__ == '__main__':
    main ()


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
