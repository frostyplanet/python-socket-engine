#!/usr/bin/env python
# coding:utf-8


from socket_engine import Connection, ReadNonBlockError, WriteNonblockError, PeerCloseError, TCPSocketEngine
from coro_engine import CoroEngine, WaitableEvent
import traceback
import socket
import errno
import threading
import thread
import time
import sys
import fcntl
import types

class EngineEvent (WaitableEvent):

    def __init__ (self):
        self.ret = None
        self.error = None

    def fire (self):
        if self.error is not None:
            raise self.error
        return self.ret

class CoroConnection(Connection):
    
    def __init__ (self, engine, *args, **k_args):
        Connection.__init__ (self, *args, **k_args)
        self.engine = engine

    def _read_cb (self, conn, event):
        event.ret = conn.get_readbuf ()
        event.error = conn.error
        self.engine.coroengine.resume_from_waitable (event)

    def _write_cb (self, conn, event):
        event.error = conn.error
        self.engine.coroengine.resume_from_waitable (event)

    def read (self, expect_len):
        event = EngineEvent ()
        self.engine.read_unblock (self, expect_len, self._read_cb, self._read_cb, cb_args=(event,))
        return event

    def write (self, buf):
        event = EngineEvent ()
        event.ret = len(buf)
        self.engine.write_unblock (self, buf, self._write_cb, self._write_cb, cb_args=(event, ))
        return event

    def readline (self, maxlen):
        event = EngineEvent ()
        self.engine.readline_unblock (self, maxlen, self._read_cb, self._read_cb, cb_args=(event,))
        return event

    def _close (self):
        Connection.close (self)

    def close (self):
        self.engine.close_conn ()

       

class CoroSocketEngine (TCPSocketEngine):

    
    def __init__ (self, *args, **k_args):
        """ 
        sock:   sock to listen
            """
        TCPSocketEngine.__init__ (self, *args, **k_args)
        self.coroengine = CoroEngine ()
        

    def put_sock (self, sock, readable_cb, readable_cb_args=(), idle_timeout_cb=None, stack=True):
        conn = CoroConnection (self, sock,
                readable_cb=readable_cb, readable_cb_args=readable_cb_args, 
                idle_timeout_cb=idle_timeout_cb)
        if stack and self._debug:
            conn.putsock_tb = traceback.extract_stack()[0:-1]
        self.watch_conn (conn)
        return conn


    def _conn_callback (self, conn, cb, args, stack=None, count=1):
        if conn.error is not None:
            self.close_conn (conn) #NOTICE: we will close the conn before err_cb
        if not callable (cb):
            return
        if conn.stack_count < self.STACK_DEPTH:
            conn.stack_count += count
            #try:
            r = cb (*args)
            if r and isinstance (r, types.GeneratorType):
                self.coroengine.run_coro (r)
                self.coroengine.poll ()
        else:
            conn.stack_count = 0
            self._lock ()
            self._cbs.append ((cb, args, stack))
            self._unlock ()


    def _exec_callback (self, cb, args, stack=None):
        try:
            r = cb (*args)
            if r and isinstance (r, types.GeneratorType):
                self.coroengine.run_coro (r)
                self.coroengine.poll ()
        except Exception, e:
            msg = "uncaught %s exception in %s %s:%s" % (type(e), str(cb), str(args), str(e))
            if stack:
                l_out = stack
                exc_type, exc_value, exc_traceback = sys.exc_info()
                l_in = traceback.extract_tb (exc_traceback)[1:] # 0 is here
                stack_trace = "\n".join (map (lambda f: "in '%s':%d %s() '%s'" % f, l_out + l_in))
                msg += "\nprevious stack trace [%s]" % (stack_trace)
                self.log_error (msg)
            else:
                self.log_exception (msg)
                raise e

    def run_coro (self, coro):
        if isinstance (coro, types.GeneratorType):
            self.coroengine.run_coro (coro)
        elif callable (coro):
            r = coro ()
            if isinstance (r, types.GeneratorType):
                self.coroengine.run_coro (r)
            
            

    def poll (self, timeout=100):
        """ you need to call this in a loop, return fd numbers polled each time,
            timeout is in ms.
        """
        self._poll_tid = thread.get_ident ()
        __exec_callback = self._exec_callback

        self.coroengine.poll ()

        #locking when poll may be prevent other thread to lock, but it's possible poll is not thread-safe, so we do the lazy approach
        if self._pending_fd_ops:
            self._lock ()
            fd_ops = self._pending_fd_ops
            self._pending_fd_ops = []
            self._unlock ()
            for _cb in fd_ops:
                _cb[0](_cb[1])

        if self._cbs:
            self._lock ()
            cbs = self._cbs
            self._cbs = []
            self._unlock ()
            for cb in cbs:
                __exec_callback (*cb)
        else:
            hlist = self._poll.poll (timeout)
            for h in hlist:
                __exec_callback (h[0], h[1])
        if self._checktimeout_inv > 0 and time.time() - self._last_checktimeout > self._checktimeout_inv:
            self._check_timeout ()


    def _connect_cb (self, sock, event):
        event.ret = CoroConnection (self, sock)
        self.coroengine.resume_from_waitable (event)

    def _connect_err_cb (self, error, event):
        event.error = error
        self.coroengine.resume_from_waitable (event)

    def connect_coro (self, addr, event, syn_retry=None):
        event = EngineEvent ()
        self.connect_unblock (self, addr, self._connect_cb, self._connect_err_cb, cb_args=(event, ), syn_retry=syn_retry)
        return event




# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
