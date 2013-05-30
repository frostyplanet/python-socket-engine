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


"""
    add the ability to run pure python coro (GeneratorType) in SocketEngine.
    coding regulation is simular to Bluelet.

    it will Replace Connection with CoroConnection (providing read()/write()/readline() coro operation).
    and add connect_coro (), run_coro() to SocketEngine

    use CoroSocketEngine directly or use patch_coro_engine with a SocketEngine object.
    if you need ssl you need to call patch_ssl_engine() before calling patch_coro_engine()
    
"""




def patch_coro_engine (_object):
    assert isinstance (_object, TCPSocketEngine)
    _init (_object)
    _inject_class (_object.__class__)

class EngineEvent (WaitableEvent):

    def __init__ (self):
        self.ret = None
        self.error = None

    def fire (self):
        if self.error is not None:
            raise self.error
        return self.ret

class CoroConnection(Connection):
    
    def __init__ (self, *args, **k_args):
        Connection.__init__ (self, *args, **k_args)

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

    def read_avail (self, maxlen):
        return self.engine.read_avail (self, maxlen)

    def write (self, buf):
        event = EngineEvent ()
        event.ret = len(buf)
        self.engine.write_unblock (self, buf, self._write_cb, self._write_cb, cb_args=(event, ))
        return event

    def readline (self, maxlen):
        event = EngineEvent ()
        self.engine.readline_unblock (self, maxlen, self._read_cb, self._read_cb, cb_args=(event,))
        return event


     
def _init (self):
    self.coroengine = CoroEngine ()
    self._connection_cls = CoroConnection

      

class CoroSocketEngine (TCPSocketEngine):

    
    def __init__ (self, *args, **k_args):
        """ 
        sock:   sock to listen
            """
        TCPSocketEngine.__init__ (self, *args, **k_args)
        _init (self) 



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
            self.coroengine.run (r)
    else:
        conn.stack_count = 0
        self._lock ()
        self._cbs.append ((cb, args, stack))
        self._unlock ()


def _exec_callback (self, cb, args, stack=None):
    try:
        r = cb (*args)
        if r and isinstance (r, types.GeneratorType):
            self.coroengine.run (r)
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
        self.coroengine.run (coro)
    elif callable (coro):
        r = coro ()
        if isinstance (r, types.GeneratorType):
            self.coroengine.run (r)
            
            

def poll (self, timeout=100):
    """ you need to call this in a loop, return fd numbers polled each time,
        timeout is in ms.
    """
    self._poll_tid = thread.get_ident ()
    __exec_callback = self._exec_callback

#    self.coroengine.poll ()

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
    event.ret = CoroConnection (sock)
    event.ret.engine = self
    self.coroengine.resume_from_waitable (event)

def _connect_err_cb (self, error, event):
    event.error = error
    self.coroengine.resume_from_waitable (event)

def connect_coro (self, addr, syn_retry=None):
    event = EngineEvent ()
    self.connect_unblock (addr, self._connect_cb, self._connect_err_cb, cb_args=(event, ), syn_retry=syn_retry)
    return event


try:
    from socket_engine_ssl import SSLSocketEngine

    def connect_ssl_coro (addr, syn_retry=None):
        event = EngineEvent ()
        SSLSocketEngine (self, addr, self._connect_cb, self._connect_err_cb, cb_args=(event, ), syn_retry=syn_retry)
        return event
    have_ssl = True
except ImportError:
    pass

def _funcToMethod(func,clas,method_name=None):
    """ only works for old type class """
    import new
    method = new.instancemethod(func,None,clas)
    if not method_name: method_name=func.__name__
    clas.__dict__[method_name]=method



def _inject_class (cls):
    _funcToMethod (connect_coro, cls)
    _funcToMethod (_connect_cb, cls)
    _funcToMethod (_connect_err_cb, cls)
    _funcToMethod (poll, cls)
    _funcToMethod (run_coro, cls)
    _funcToMethod (_exec_callback, cls)
    _funcToMethod (_conn_callback, cls)

    if cls.__dict__.has_key ("connect_unblock_ssl"):
        _funcToMethod (connect_ssl_coro, cls)

_inject_class (CoroSocketEngine)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
