#!/usr/bin/env python
# coding:utf-8

import os
import _env
import socket
from lib.rpc import SSL_RPC_Client
from lib.rpc_server import SSL_RPC_Server
from lib.log import Log
import time
import threading

import conf

SSL_CERT = os.path.join(os.path.dirname(__file__), '../private/server.pem')
SERVER_ADDR = ("127.0.0.1", 12346)

def main ():

    def foo (arg1, arg2):
        return (arg1, arg2)

    def bar ():
        raise Exception ("orz")
        
    server = SSL_RPC_Server (SSL_CERT, 
            SERVER_ADDR,
            Log ("server", config=conf),
            white_list=("127.0.0.1", ),
            )
    server.add_handle (foo)
    server.add_handle (bar)
    server.start (5)
    print "server started"
    def __run_server ():
        print "run server"
        server.loop ()
        return
    th = threading.Thread (target=__run_server)
    th.setDaemon (1)
    th.start ()
    time.sleep (1)
    print "starting client"
    client = SSL_RPC_Client (Log ("client", config=conf))
    client.set_timeout (5)
    client.connect (SERVER_ADDR)
    print "connected"
    ret = client.call ("foo", "aaa", arg2="bbb")
    print "foo => ret"
    try:
        client.call ("bar")
    except Exception, e:
        print "bar", e
    client.close ()

if __name__ == '__main__':
    main ()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
