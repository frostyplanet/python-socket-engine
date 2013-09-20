#!/usr/bin/env python
# coding:utf-8

import os
import _env
import socket
from lib.rpc import AES_RPC_Client, random_string
from lib.rpc_server import AES_RPC_Server
from lib.log import Log
import time
import threading
from lib.attr_wrapper import AttrWrapper

import conf

SERVER_ADDR = ("127.0.0.1", 12346)

class View():
    def foo(self, arg1, arg2):
        return(arg1, arg2, {'dd': {'ee': 1}})

    def bar(self):
        raise Exception("orz")
 

def main():

    key = "sddjou34324523432gh45t452354"
    server = AES_RPC_Server( 
            SERVER_ADDR,
            client_keys={'127.0.0.1': key},
            logger=Log("server", config=conf),
            )
    server.add_view(View())
    server.start(5)
    print "server started"
    def __run_server():
        print "run server"
        server.loop()
        return
    th = threading.Thread(target=__run_server)
    th.setDaemon(1)
    th.start()
    time.sleep(1)
    print "starting client"
    client = AES_RPC_Client(key, Log("client", config=conf))
    client.set_timeout(5)
    client.connect(SERVER_ADDR)
    print "connected"
    ret = client.call("foo", "aaa", arg2="bbb")
    assert ret == ("aaa", "bbb", {'dd': {'ee': 1}})
    val = AttrWrapper.wrap(ret)
    print "ret[2]['dd']['ee']", val[2].dd.ee
    print "foo => ret"
    try:
        client.call("bar")
    except Exception, e:
        print "bar", e
    client.close()

if __name__ == '__main__':
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
