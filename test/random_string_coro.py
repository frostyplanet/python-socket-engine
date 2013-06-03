#!/usr/bin/env python
# coding:utf-8


import _env
import conf
#from lib.socket_engine import TCPSocketEngine, Connection
from lib.socket_engine_coro import CoroSocketEngine
from lib.net_io import send_all, recv_all, NetHead
import socket
import threading
import random
import time
from lib.log import Log, getLogger
import lib.io_poll as io_poll
#from lib.conn_pool import *
import os
import traceback
import string
#from lib.timecache import TimeCache

global_lock = threading.Lock ()

server_addr = ("0.0.0.0", 20300)
g_round = 500

g_send_count = 0
g_client_num = 20
g_done_client = 0

MAX_LEN = 8 * 1024

def random_string (n):
    s = string.ascii_letters + string.digits
    result = ""
    for i in xrange (n):
        result += random.choice (s)
    return result


def start_echo_server ():
    global server_addr
    poll = io_poll.get_poll()
    print str(poll)
    server = CoroSocketEngine (poll, is_blocking=False)
    server.set_logger (getLogger ("server"))

    def _on_readable (conn):
        buf, eof = conn.read_avail (4096)
        if buf:
            #print "write", len(buf)
            yield conn.write (buf)
        if eof:
            conn.close ()
        else:
            conn.watch ()
        return
    server.listen_addr (server_addr, readable_cb=_on_readable)

    def _run (_server):
        while True:
            try:
                _server.poll ()
            except Exception, e:
                traceback.print_exc ()
                os._exit (1)
        return
    th = threading.Thread (target=_run, args=(server,))
    th.setDaemon (1)
    th.start ()
    return server
 

def test_client ():
    global g_done_client, g_client_num
##    pool = ConnPool (10, -1)
    i = 0
    ths = list ()
    start_time = time.time ()
    def client (engine, client_id, server_addr, _round):
        global g_done_client, global_lock
        try:
            conn = yield engine.connect_coro (server_addr)
            for i in xrange (_round):
                l = random.randint(1, MAX_LEN)
                data = random_string (l)
        #        print l, len(data)
                yield conn.write (data)
                _data = yield conn.read (len (data))
                if _data == data:
                    pass
                    #print "client", i
                else:
                    #global_lock.acquire ()
                    conn.close ()
                    print "client recv invalid data", i, len(_data), len(data), l
                    os._exit (1)
                    return
            conn.close ()
            global_lock.acquire ()
            g_done_client += 1
            print "client done", g_done_client
            if g_done_client == g_client_num:
                print "time:", time.time () - start_time
                global_lock.release ()
                os._exit (0)
            global_lock.release ()
        except socket.error, e:
            engine.logger.exception (e)
            print e
            os._exit (1)
        return

    engine = CoroSocketEngine (io_poll.get_poll ())
    engine.set_logger (getLogger ("client"))
    for i in xrange (g_client_num):
        engine.run_coro (client (engine, i, server_addr, g_round))
    while True:
        engine.poll ()


def main ():
    Log ("client", config=conf)
    Log ("server", config=conf)
    server = start_echo_server ()
    time.sleep (1)
    test_client ()

if __name__ == '__main__':
    main ()



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
