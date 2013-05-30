#!/usr/bin/env python
# coding:utf-8


from socket_engine import Connection, ReadNonBlockError, WriteNonblockError, PeerCloseError, TCPSocketEngine, ConnState
from coro_engine import CoroEngine, EngineEvent
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


class CoroConnection(Connection):
    
    def __init__ (self, *args, **k_args):
        Connection.__init__ (self, *args, **k_args)


    def read (self, expect_len):
        return self.engine.read_coro (self, expect_len)

    def read_avail (self, maxlen):
        return self.engine.read_avail (self, maxlen)

    def write (self, buf):
        return self.engine.write_coro (self, buf)

    def readline (self, maxlen):
        return self.engine.readline_coro (self, maxlen)


     
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
    event.done = True
    self.coroengine.resume_from_waitable (event)

def _connect_err_cb (self, error, event):
    event.error = error
    event.done = True
    self.coroengine.resume_from_waitable (event)

def connect_coro (self, addr, syn_retry=None):
    event = EngineEvent ()
    self.connect_unblock (addr, self._connect_cb, self._connect_err_cb, cb_args=(event, ), syn_retry=syn_retry)
    return event

def _read_cb (self, conn, event):
    event.ret = conn.rd_buf
    event.error = conn.error
    event.done = True
    self.coroengine.resume_from_waitable (event)

def _write_cb (self, conn, event):
    event.error = conn.error
    event.done = True
    self.coroengine.resume_from_waitable (event)



def read_coro (self, conn, expect_len):
    """ 
        read fixed len data
        on timeout/error, err_cb will be called, the connection will be close afterward, 
    """
    assert isinstance (conn, Connection)
    assert expect_len > 0
    ahead_len = len (conn.rd_ahead_buf)
    event = EngineEvent ()
    if ahead_len:
        if conn.error is not None:
            event.error = conn.error
            event.done
            return event
        elif ahead_len >= expect_len:
            conn.rd_buf = conn.rd_ahead_buf[0:expect_len]
            conn.rd_ahead_buf = conn.rd_ahead_buf[expect_len:]
            event.ret = conn.rd_buf
            event.done = True
            return event
        else:
            conn.rd_buf = conn.rd_ahead_buf
            conn.rd_ahead_buf = ""
            conn.rd_expect_len = expect_len - ahead_len
    else:
        conn.rd_buf = ""
        conn.rd_expect_len = expect_len
    conn.status_rd = ConnState.TOREAD
    conn.read_cb_args = (event, )
    conn.read_err_cb = self._read_cb
    if self._do_unblock_read (conn, self._read_cb, direct=True):
        event.error = conn.error
        event.ret = conn.rd_buf
        event.done = True
    return event

def write_coro (self, conn, buf):
    """    NOTE: write only temporaryly register for write event, will not effect read
        """
    assert isinstance (conn, Connection)
    conn.status_wr = ConnState.TOWRITE
    conn.wr_offset = 0
    conn.write_err_cb = self._write_cb
    event = EngineEvent ()
    conn.write_cb_args = (event, )
    if self._do_unblock_write (conn, buf, self._write_cb, direct=True):
        event.error = conn.error
        event.ret = len (buf)
        event.done = True
    return event

def readline_coro (self, conn, max_len):
    """ 
        read until '\n' is received or max_len is reached.
        if the line is longer than max_len, a Exception(line maxlength exceed) will be in conn.error which received by err_cb()
        on timeout/error, err_cb will be called, the connection will be close afterward, 
        you must not do it yourself, any operation that will lock the server is forbident in err_cb ().
        ok_cb/err_cb param: conn, *cb_args
        NOTE: when done, you have to watch_conn or remove_conn by yourself
        """
    assert isinstance (conn, Connection)
    conn.status_rd = ConnState.TOREAD
    conn.rd_buf = ""
    event = EngineEvent ()
    conn.read_cb_args = (event, )
    conn.read_err_cb = self._read_cb
    if self._do_unblock_readline (conn, self._read_cb, max_len, direct=True):
        event.error = conn.error
        event.ret = conn.rd_buf
        event.done = True
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
    _funcToMethod (read_coro, cls)
    _funcToMethod (write_coro, cls)
    _funcToMethod (readline_coro, cls)
    _funcToMethod (run_coro, cls)

    _funcToMethod (_connect_cb, cls)
    _funcToMethod (_connect_err_cb, cls)
    _funcToMethod (poll, cls)
    _funcToMethod (_exec_callback, cls)
    _funcToMethod (_conn_callback, cls)
    _funcToMethod (_read_cb, cls)
    _funcToMethod (_write_cb, cls)

    if cls.__dict__.has_key ("connect_unblock_ssl"):
        _funcToMethod (connect_ssl_coro, cls)

_inject_class (CoroSocketEngine)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
