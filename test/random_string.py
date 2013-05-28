#!/usr/bin/env python
# coding:utf-8


import _env
import conf
from lib.socket_engine import TCPSocketEngine, Connection
from lib.net_io import send_all, recv_all, NetHead
import socket
import threading
import random
import time
from lib.log import Log, getLogger
import lib.io_poll as iopoll
#from lib.conn_pool import *
import os
import traceback
import string
#from lib.timecache import TimeCache

global_lock = threading.Lock ()

server_addr = ("0.0.0.0", 20300)
g_round = 50

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
    poll = None
    if 'EPoll' in dir(iopoll):
        poll = iopoll.EPoll (True)
        print "using epoll et mode"
    else:
        poll = iopoll.Poll ()
    server = TCPSocketEngine (poll, is_blocking=False, debug=False)
    server.set_logger (getLogger ("server"))
#    server.get_time = tc.time

    def _on_readable (conn):
        def __on_send (conn):
            #print "write_ok"
            #_on_readable (conn)
            server.watch_conn (conn)
            return
        buf, eof = server.read_avail (conn, 4096)
        if buf:
            #print "write", len(buf)
            server.write_unblock (conn, buf, __on_send, None)
        elif eof:
            server.close_conn (conn)
        else:
            server.watch_conn (conn)
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
 
def client ():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    global g_send_count, g_client_num, g_done_client, server_addr, global_lock
    global g_round
    sock.connect (server_addr)
#        times = random.randint (1, 5000)
#        time.sleep (times/ 2000.0)
    for i in xrange (0, g_round):
        l = random.randint(1, MAX_LEN)
        data = random_string (l)
        send_all (sock, data)
#        print l, len(data)
        _data = recv_all (sock, l)
        if _data == data:
            #print "client", i
            global_lock.acquire ()
            g_send_count += 1
            global_lock.release ()
        else:
            global_lock.acquire ()
            print "client recv invalid data", i, len(_data), len(data), l
            global_lock.release ()
            os._exit (0)
#            time.sleep (0.01)
    print "client done", g_done_client
    sock.close ()
    global_lock.acquire ()
    g_done_client += 1
    global_lock.release ()

def test_client ():
    global g_send_count, g_done_client, g_client_num
##    pool = ConnPool (10, -1)
    i = 0
    ths = list ()
    start_time = time.time ()
    while True:
        if i < g_client_num:
#            ths.append (threading.Thread (target=client_pool, args=(pool, )))
            ths.append (threading.Thread (target=client, args=()))
            ths[i].setDaemon(1)
            ths[i].start ()
            i += 1
        else:
            for j in xrange (0, i):
                ths[j].join ()

            print "time:", time.time () - start_time
            print g_done_client, g_send_count
#           pool.clear_conn (server_addr)

            if g_client_num == g_done_client:
                print "test OK"
                os._exit (0)
            else:
                print "test fail"
            return

def test_client_line ():
    poll = None
    if 'EPoll' in dir(iopoll):
        poll = iopoll.EPoll (True)
        print "client using epoll et mode"
    else:
        poll = iopoll.Poll ()
    engine = TCPSocketEngine (poll, debug=False)
#    engine.get_time = tc.time
    engine.set_logger (getLogger ("client"))
    start_time = time.time ()
    def __on_conn_err (e, client_id):
        print client_id, "connect error", str(e)
        os._exit (1)
        return
    def __on_err (conn, client_id, count, *args):
        print client_id, "error", str(conn.error), count
        return
    def __on_recv (conn, client_id, count, data):
        global g_done_client
        if count >= 0 and data:
            buf = conn.get_readbuf ()
            if buf != data:
                print "data recv invalid, client:%s, count:%s, data:[%s]" % (client_id, count, buf)
                os._exit (0)
        if count < g_round:
            #print client_id, count
            l = random.randint(1, MAX_LEN -1)
            newdata = random_string (l)
            engine.write_unblock (conn, newdata, __on_send, __on_err, (client_id, count + 1, newdata))
        else:
            engine.close_conn (conn)
            g_done_client += 1
            print "client", client_id, "done"
            if g_done_client == g_client_num:
                print "test client done time: ", time.time() - start_time
                os._exit (0)
        return
    def __on_send ( conn, client_id, count, data):
#        print "send", client_id, count, "len", len(data)
        engine.read_unblock (conn, len(data), __on_recv, __on_err, (client_id, count, data))
        return
    def __on_conn (sock, client_id):
#        print "conn", client_id, time.time()
        __on_recv (Connection (sock), client_id, -1, None)
        return
    def _run (engine):
        global g_done_client
        while g_done_client < g_client_num:
            try:
                engine.poll ()
            except Exception, e:
                traceback.print_exc ()
                os._exit (1)
        print g_done_client
        return
    print "client_unblock started"
    for i in xrange (0, g_client_num):
#        print "conning", i
        engine.connect_unblock (server_addr, __on_conn, __on_conn_err, (i,))
    _run (engine)  




def main ():
    Log ("client", config=conf)
    Log ("server", config=conf)
    server = start_echo_server ()
    time.sleep (1)
    test_client ()
    #test_client_line ()

if __name__ == '__main__':
    main ()



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
