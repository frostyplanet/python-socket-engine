#!/usr/bin/env python
# coding:utf-8

import _env
import conf
from lib.socket_engine_coro import CoroSocketEngine, PeerCloseError
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
#from lib.timecache import TimeCache

data = "".join(["1234567890" for i in xrange(0, 10000)])
global_lock = threading.Lock()

server_addr = ("0.0.0.0", 20300)
g_round = 50000

g_send_count = 0
g_client_num = 4
g_done_client = 0

#tc = TimeCache(0.5)



def client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    global g_send_count, g_client_num, g_done_client, server_addr, global_lock
    global data
    global g_round
    sock.connect(server_addr)
#        times = random.randint(1, 5000)
#        time.sleep(times/ 2000.0)
    for i in xrange(0, g_round):
        send_all(sock, data)
        _data = recv_all(sock, len(data))
        if _data == data:
            global_lock.acquire()
            g_send_count += 1
            global_lock.release()
        else:
            print "client recv invalid data"
#            time.sleep(0.01)
    print "client done", g_done_client
    sock.close()
    global_lock.acquire()
    g_done_client += 1
    global_lock.release()

 
def test_client():
    global g_send_count, g_done_client, g_client_num
##    pool = ConnPool(10, -1)
    i = 0
    ths = list()
    start_time = time.time()
    while True:
        if i < g_client_num:
#            ths.append(threading.Thread(target=client_pool, args=(pool, )))
            ths.append(threading.Thread(target=client, args=()))
            ths[i].setDaemon(1)
            ths[i].start()
            i += 1
        else:
            for j in xrange(0, i):
                ths[j].join()

            print "time:", time.time() - start_time
            print g_done_client, g_send_count
#           pool.clear_conn(server_addr)

            if g_client_num == g_done_client:
                print "test OK"
            else:
                print "test fail"
            return



def start_coro_server(poll=None):
    global server_addr
    poll = iopoll.get_poll()
    server = CoroSocketEngine(poll, is_blocking=False, debug=False)
    server.set_logger(getLogger("server"))
#    server.get_time = tc.time
    print "starting unblock server with", str(poll)
    def _handler(conn):
        try:
            buf = yield conn.read(len(data))
            yield conn.write(buf)
            server.watch_conn(conn)
        except PeerCloseError:
            pass
        except Exception, e:
            getLogger("server").exception(e)
            print e
        return
    server.listen_addr(server_addr, _handler)

#    def _handler2(conn):
#        try:
#            yield conn.write(conn.get_readbuf())
#            server.watch_conn(conn)
#        except PeerCloseError:
#            #print "peerclose"
#            pass
#        except Exception, e:
#            getLogger("server").exception(e)
#            print e
#        return
#    server.listen_addr(server_addr, readable_cb=server.read_unblock, readable_cb_args=(len(data), _handler2))



    def _run(_server):
        while True:
            try:
                _server.poll()
            except Exception, e:
                traceback.print_exc()
                os._exit(1)
        return
    th = threading.Thread(target=_run, args=(server,))
    th.setDaemon(1)
    th.start()
    return server
 
def main():
    Log("client", config=conf)
    Log("server", config=conf)
    server = start_coro_server()
#    server = start_block_server()
    time.sleep(1)
    test_client()
    while server.coroengine.threads:
        print "waiting for coro ends", server.coroengine.threads
        time.sleep(1)
#    test_client_unblock()

if __name__ == '__main__':
#    import yappi
#    yappi.start()
    main()
#    yappi.print_stats()



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
