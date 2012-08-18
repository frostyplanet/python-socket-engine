#!/usr/bin/env python


import _env
from lib.socket_engine import TCPSocketEngine, Connection
import socket
import unittest
import lib.io_poll as iopoll
from lib.log import Log, getLogger
import os
import threading
import time
import sys
import traceback
import random
import errno
import config


class SocketEngineTest (object):
    
    th = None
    running = False
    engine = None

    server_addr = None
    server_sock = None

    def __init__ (self):
        self.engine = TCPSocketEngine (iopoll.Poll ())
        self.engine.set_logger (Log ("test", config=config))
        self.engine.set_timeout (5, 5)

    def start_client (self):
        assert not self.running
        self.running = True
        def _run (self):
            print "client started"
            while self.running:
                try:
                    l = self.engine.poll (1)
                except Exception, e:
                    traceback.print_exc ()
                    os._exit (1)
            return
        self.th = threading.Thread (target=_run, args=(self, ))
        self.th.setDaemon (1)
        self.th.start ()

    def start_server (self, server_addr, readable_cb, readable_cb_args=(), idle_timeout_cb=None, new_conn_cb=None):
        assert not self.running
        self.running = True
        def _run (self):
            print "server started"
            while self.running:
                try:
                    self.engine.poll (1)
                except Exception, e:
                    traceback.print_exc ()
                    os._exit (1)
            return
        self.th = threading.Thread (target=_run, args=(self, ))
        self.th.setDaemon (1)
        self.th.start ()

        self.server_addr = server_addr
        self.server_sock = self.engine.listen_addr (server_addr, readable_cb=readable_cb, 
                readable_cb_args=readable_cb_args, 
                idle_timeout_cb=idle_timeout_cb, 
                new_conn_cb=new_conn_cb)
          
    def stop (self):
        if not self.th:
            return
        self.running = False
        while self.th.isAlive ():
            time.sleep (1)
        if self.server_sock:
            self.engine._poll.unregister (self.server_sock.fileno ())
            self.server_sock.close ()
        print "stopped"

########### handler functions ############

def __on_echo_server_error (conn, *args):
    print >>sys.stderr, write ("!!! server error: %s\n" % (str (conn.error)))

def echo_server (conn, engine):
    try:
        temp = conn.sock.recv (1024)
        engine.write_unblock (conn, temp, engine.watch_conn, __on_echo_server_error)
    except socket.error, e:
        __on_echo_server_error (conn, e)
        engine.close_conn (conn)



################## test cases #################

class TestConnect (unittest.TestCase):

    server = None
    client = None
    data = "".join (["0" for i in xrange (0, 10000)])
    server_addr = ("127.0.0.1", 12033)

    def setUp (self):
        self.server = SocketEngineTest ()
        self.client = SocketEngineTest ()
        self.server.start_server (self.server_addr, readable_cb=echo_server, readable_cb_args=(self.server.engine,))
        self.client.start_client ()
        print "[startup]", str (self)

    def tearDown (self):
        if self.server:
            self.server.stop ()
        if self.client:
            self.client.stop ()

    def test_connect (self):
        event = threading.Event ()
        def __on_err (conn):
            print conn.error
            raise Exception (conn.error)
        def __on_conn_err (e):
            print e
            raise Exception ("conn" + str(e))
        def __on_read (conn):
            print "read"
            self.client.engine.close_conn (conn)
            buf = conn.get_readbuf ()
            if buf == self.data:
                event.set ()
            else:
                self.fail ("test connect error, invalid data received: %s" % (buf))
        def __on_write (conn):
            print "write"
            self.client.engine.read_unblock (conn, len (self.data), __on_read, __on_err)
            return
        def __on_conn (sock):
            print "on connect"
            self.client.engine.write_unblock (Connection (sock), self.data, __on_write, __on_err)
            return
        self.client.engine.connect_unblock (self.server_addr, __on_conn, __on_conn_err)
        print "connect unblock"
        event.wait ()
        print "* test connect ok"

    def test_connect_fail (self):
        event = threading.Event ()
        engine = self.client.engine
        def __on_conn_err (e):
            event.set ()
        def __on_conn (conn):
            self.fail ("imposible")
            engine.close_conn (conn)
        self.client.engine.connect_unblock (("127.0.0.1", 12025), __on_conn, __on_conn_err)
        event.wait ()
        print "* test connect to unlistened addr ok"

    def test_connect_failresolve (self):
        event = threading.Event ()
        engine = self.client.engine
        def __on_conn_err (e):
            event.set ()
        def __on_conn (conn):
            self.fail ("imposible")
            engine.close_conn (conn)
        self.client.engine.connect_unblock (("aaaaaaaaaaaa", 12025), __on_conn, __on_conn_err)
        event.wait ()
        print "* test connect to invalid addr ok"



class TestReadTimeout (unittest.TestCase):

    server = None
    client = None
    data = "".join (["0" for i in xrange (0, 100)])
    server_addr = ("127.0.0.1", 12033)

    def setUp (self):
        self.server = SocketEngineTest ()
        self.client = SocketEngineTest ()
        self.server.start_server (self.server_addr, readable_cb=echo_server, readable_cb_args=(self.server.engine, ))
        self.client.start_client ()
        print "[start]", str (self)

    def tearDown (self):
        if self.server:
            self.server.stop ()
        if self.client:
            self.client.stop ()

    def test_read_timeout (self):
        self.server.engine.set_timeout (0, 0)
        self.client.engine.set_timeout (idle_timeout=0, rw_timeout=1)
        event = threading.Event ()
        engine = self.client.engine
        def __on_expected_error (conn):
            print "get expected error", conn.error
            event.set ()
        def __on_err (conn):
            self.fail ("unexpected error: " + str (conn.error))
        def __on_read_impossible (conn):
            self.fail ("imposible")
            engine.close_conn (conn)
        def __on_write (conn):
            print "on write"
            engine.read_unblock (conn, len (self.data) * 2, __on_read_impossible, __on_expected_error)
        def __on_conn_err (e, *args):
            self.fail ("connect failed: "+ str(e))
        def __on_conn (sock):
            print "on connect"
            engine.write_unblock (Connection (sock), self.data, __on_write, __on_err)
            return
        self.client.engine.connect_unblock (self.server_addr, __on_conn, __on_conn_err)
        event.wait ()
        print "* connection rd_timeout test ok"

class TestWriteTimeout (unittest.TestCase):

    server = None
    client = None
    data = "".join (["0" for i in xrange (0, 1000000)])
    server_addr = ("127.0.0.1", 12033)
    hang_conn = None

    def setUp (self):
        self.server = SocketEngineTest ()
        self.client = SocketEngineTest ()
        self.client.start_client ()
        print "[start]", str (self)

    def testwrtimeout (self):
        def __readable (conn):
            self.hang_conn = conn
            self.server.engine.remove_conn (conn)
        self.server.start_server (self.server_addr, __readable)
        self.server.engine.set_timeout (0, 0)
        event = threading.Event ()
        def __on_expected_error (conn):
            print "expected error: " + str (conn.error)
            event.set ()
        def __on_write (conn):
            self.client.engine.close_conn (conn)
            self.fail ("can believe the socket buffer is so large, you can try to increase the data size! ")
        def __on_conn_err (e, *args):
            self.fail ("connect failed: "+ str(e))
        def __on_conn (sock):
            print "on connect"
            self.client.engine.write_unblock (Connection (sock), self.data, __on_write, __on_expected_error)
            return
        self.client.engine.set_timeout (idle_timeout=0, rw_timeout=1)
        self.client.engine.connect_unblock (self.server_addr, __on_conn, __on_conn_err)
        event.wait ()
        print "* test write timeout OK"

    def tearDown (self):
        if self.hang_conn:
            self.hang_conn.close ()
        if self.server:
            self.server.stop ()
        if self.client:
            self.client.stop ()

class TestIdleTimeout (unittest.TestCase):
    server = None
    client = None
    server_addr = ("127.0.0.1", 12033)
    data = "".join (["0" for i in xrange (0, 100)])
    hang_conn = None

    def setUp (self):
        self.server = SocketEngineTest ()
        self.client = SocketEngineTest ()
        self.client.start_client ()
        print "[start]", str (self)

    def tearDown (self):
        if self.hang_conn:
            self.hang_conn.close ()
        if self.server:
            self.server.stop ()
        if self.client:
            self.client.stop ()
    
    def testidletimeout (self):
        self.client.engine.set_timeout (idle_timeout=0, rw_timeout=0)
        event = threading.Event ()
        def __idle_timeout_cb (conn, *args):
            print "idle callback"
            event.set ()
            return
        self.server.start_server (self.server_addr, readable_cb=echo_server, readable_cb_args=(self.server.engine, ), idle_timeout_cb=__idle_timeout_cb)
        self.server.engine.set_timeout (idle_timeout=2, rw_timeout=0)
        def __on_err (conn):
            self.fail ("unexpected error: " + str (conn.error))
        def __on_read (conn):
            self.hang_conn = conn
            self.client.engine.remove_conn (conn)
        def __on_write (conn):
            self.client.engine.read_unblock (conn, len (self.data), __on_read, __on_err)
        def __on_conn_err (e, *args):
            self.fail ("connect failed: "+ str(e))
        def __on_conn (sock):
            print "on connect"
            self.client.engine.write_unblock (Connection (sock), self.data, __on_write, __on_err)
            return
        self.client.engine.connect_unblock (self.server_addr, __on_conn, __on_conn_err)
        event.wait () 
        print "* test idle timeout OK"


if __name__ == '__main__':
    unittest.main ()




# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
