#!/usr/bin/env python

# frostyplanet@gmail.com
# which is intend to used as backend of socket_engine.py

try:
    import epoll as select # python-epoll provide the same interface as select.poll, which unlike 2.6's select.epoll
except ImportError:
    import select
import errno

class Poll (object):
    _handles = None
    _poll = None
    _in = select.POLLIN
    _out = select.POLLOUT
    _in_real = select.POLLIN | select.POLLPRI | select.POLLERR | select.POLLHUP | select.POLLNVAL
    _out_real = select.POLLOUT | select.POLLERR | select.POLLHUP | select.POLLNVAL
    _timeout_scale = 1

    def __init__ (self, debug=False):
        self._handles = dict ()
        self.debug = debug
        self._poll = select.poll ()

    def register (self, fd, event, handler, handler_args=()):
        handler_args = handler_args or ()
        assert event in ['r', 'w']
        data = self._handles.get (fd)
        if not data:
            if event == 'r':
                self._handles[fd] = [(handler, handler_args, ), None]
                self._poll.register (fd, self._in)
            else: # w
                self._handles[fd] = [None, (handler, handler_args, )]
                self._poll.register (fd, self._out)
        else: # one call to register can be significant overhead
            if event == 'r':
                if data[1]:
                    self._poll.modify (fd, self._in | self._out)
                data[0] = (handler, handler_args, )
            else: # w
                if data[0]:
                    self._poll.modify (fd, self._in | self._out)
                data[1] = (handler, handler_args, )

    def unregister (self, fd, event='r'):
        assert event in ['r', 'w', 'rw', 'all']
        data = self._handles.get (fd)
        if not data:
            return
        if event == 'r':
            if not data[0]:
                return
            if data[1]: # write remains
                self._poll.modify (fd, self._out)
                data[0] = None
                return
        elif event == 'w':
            if not data[1]:
                return
            if data[0]:
                self._poll.modify (fd, self._in)
                data[1] = None
                return
        try:
            del self._handles[fd]
            self._poll.unregister (fd)
        except KeyError:
            pass


    def poll (self, timeout):
        """ 
            timeout is in milliseconds in consitent with poll.
            return [(function, arg), ...] to exec
            """
        while True:
            try:
                plist = self._poll.poll (timeout/ self._timeout_scale) # fd, event
                hlist = []
                for fd, event in plist:
                    data = self._handles.get (fd)
                    if not data:
                        raise Exception ("bug")
                    else:
                        if event & self._in_real:
                            if data[0]:
                                hlist.append (data[0])
                            elif event & self._in:
                                raise Exception ("bug")
                        if event & self._out_real:
                            if data[1]:
                                hlist.append (data[1])
                            elif event & self._out:
                                raise Exception ("bug")
                return hlist
            except select.error, e:
                if e[0] == errno.EINTR:
                    continue
                raise e



if 'epoll' in dir(select):

    class EPoll (Poll):
        _handles = None
        _poll = None
        _in = select.EPOLLIN
        _out = select.EPOLLOUT
        _in_real = select.EPOLLIN | select.EPOLLRDBAND | select.EPOLLPRI | select.EPOLLHUP | select.EPOLLERR
        _out_real = select.EPOLLOUT | select.EPOLLWRBAND | select.EPOLLHUP | select.EPOLLERR 
        _timeout_scale = 1000.0

        def __init__ (self, is_edge=True):
            self.is_edge = is_edge
            self._handles = dict ()
            self._poll = select.epoll ()
            if self.is_edge:
                self._in = select.EPOLLET | select.EPOLLIN
                self._out = select.EPOLLET | select.EPOLLOUT
            else:
                self._in = select.EPOLLIN
                self._out = select.EPOLLOUT
            

               

                

def get_poll ():
    if 'epoll' in dir(select):
        print "e"
        return EPoll ()
    else:
        return Poll ()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
