#!/usr/bin/env python
# coding:utf-8

import _env
import lib.io_poll as io_poll
import unittest
import os
import sys
import threading
import time

class TestPoll (unittest.TestCase):

    def cb1 (self):
        pass

    def cb2 (self):
        pass

    def _test_1 (self, poll):
        rd, wr = os.pipe ()
        poll.register (rd, 'r', self.cb1, )
        data = poll._handles.get (rd)
        self.assert_ (data and data[0])
        self.assertEqual (data[0][0], self.cb1)
        self.assertEqual (data[0][1], ())
        poll.register (rd, 'w', self.cb2, (1, ))
        self.assert_ (data[1])
        self.assertEqual (data[0][0], self.cb1)
        self.assertEqual (data[1][0], self.cb2)
        self.assertEqual (data[1][1], (1, ))
        poll.unregister (rd, 'w')
        self.assertEqual (data[0][0], self.cb1)
        self.assertEqual (data[1], None)
        poll.unregister (rd, 'w')
        data = poll._handles.get (rd)
        self.assert_ (data)
        self.assertEqual (data[0][0], self.cb1)
        self.assertEqual (data[1], None)
        poll.unregister (rd, 'r')
        data = poll._handles.get (rd)
        self.assert_ (not data)
        os.close (rd)
        os.close (wr)

    def _exec_cbs (self, hlist):
        for h in hlist:
            h[0] (*h[1])

    def _test_2 (self, poll):
        rd, wr = os.pipe ()
        print "pipe rd", rd, "wr", wr
        ev1 = threading.Event ()
        ev2 = threading.Event ()
        def __cb1 ():
            print "test 2 cb1"
            ev1.set ()
            return
        def __cb2 ():
            print "test2 cb2"
            ev2.set ()
            return
        poll.register (rd, 'r', __cb1)
        poll.register (wr, 'w', __cb2)
        self._exec_cbs (poll.poll (1))
        self.assert_ (not ev1.is_set ())
        self.assert_ (ev2.is_set ())
        ev1.clear ()
        ev2.clear ()
        os.write (wr, "a")
        self._exec_cbs (poll.poll (1))
        self.assert_ (ev1.is_set ())
        self.assert_ (ev2.is_set ())
        self.assertEqual (os.read (rd, 1), 'a')
        ev1.clear ()
        self._exec_cbs (poll.poll (1))
        self.assert_ (not ev1.is_set ())
        os.close (wr)
        ev1.clear ()
        ev2.clear ()
        self._exec_cbs (poll.poll (1))
        self.assert_ (ev1.is_set ())
#        self.assert_ (ev2.is_set ()) # not work for libev
        self.assertEqual (os.read (rd, 1), '')
        self.assertEqual (os.read (rd, 1), '')
        os.close (rd)
        self.assert_ (poll.unregister (rd, 'r'))
        self.assert_ (poll.unregister (wr, 'w'))
        ev1.clear ()
        ev2.clear ()
        print "test_2 done", str(poll)

    def _test_3 (self, poll):
        rd, wr = os.pipe ()
        print "pipe rd", rd, "wr", wr
        ev1 = threading.Event ()
        ev2 = threading.Event ()
        def __cb1 ():
            print "test3 cb1"
            ev1.set ()
            return
        def __cb2 ():
            print "test3 cb2"
            ev2.set ()
            return
        poll.register (rd, 'r', __cb1)
        poll.register (wr, 'w', __cb2)
        self._exec_cbs (poll.poll (1))
        print "poll 1"
        self.assert_ (not ev1.is_set ())
        self.assert_ (ev2.is_set ())
        ev1.clear ()
        ev2.clear ()
        os.write (wr, "a")
        self._exec_cbs (poll.poll (1))
        print "poll 2"
        self.assert_ (ev1.is_set ())
        self.assert_ (ev2.is_set ())
        self.assertEqual (os.read (rd, 1), 'a')
        ev1.clear ()
        self._exec_cbs (poll.poll (1))
        print "poll 3"
        self.assert_ (not ev1.is_set ())
        os.close (rd)
        ev1.clear ()
        ev2.clear ()
        self._exec_cbs (poll.poll (1))
#        self.assert_ (ev1.is_set ()) # not work for libev
        self.assert_ (ev2.is_set ())
        os.close (wr)
        poll.unregister (rd)
        poll.unregister (wr)
        ev1.clear ()
        ev2.clear ()
        print "test_3 done", str(poll)

#    def test_epoll (self):
#        ep = io_poll.Poll()
#        self._test_1 (ep)
#        self._test_2 (ep)
#        self._test_3 (ep)
#
#    def test_poll (self):
#        p = io_poll.Poll()
#        self._test_1 (p)
#        self._test_2 (p)
#        self._test_3 (p)
#


    def test_evpoll (self):
        if 'EVPoll' not in dir(io_poll):
            return
        print "evpoll"
        evp = io_poll.EVPoll()
        start_ts = time.time ()
        evp.poll (1000)
        self.assert_ (time.time () - start_ts > 1)

#        rd, wr = os.pipe ()
#        poll.register (rd, 'r', self.cb1, )
#        data = poll._handles.get (rd)
#        self.assert_ (data and data[0])
#        self.assertEqual (data[0][0], self.cb1)
#        self.assertEqual (data[0][1], ())
#        poll.register (rd, 'w', self.cb2, (1, ))
#        self.assert_ (data[1])
#        self.assertEqual (data[0][0], self.cb1)
#        self.assertEqual (data[1][0], self.cb2)
#        self.assertEqual (data[1][1], (1, ))
#        poll.unregister (rd, 'w')
#        self.assertEqual (data[0][0], self.cb1)
#        self.assertEqual (data[1], None)
#        poll.unregister (rd, 'w')
#        data = poll._handles.get (rd)
#        self.assert_ (data)
#        self.assertEqual (data[0][0], self.cb1)
#        self.assertEqual (data[1], None)
#        poll.unregister (rd, 'r')
#        data = poll._handles.get (rd)
#        self.assert_ (not data)
#        os.close (rd)
#        os.close (wr)

        self._test_2 (evp)
        self._test_3 (evp)
        print "try another poll"
        evp.poll (1000)


if __name__ == '__main__':
    unittest.main ()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :

