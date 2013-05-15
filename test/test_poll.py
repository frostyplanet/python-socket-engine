#!/usr/bin/env python
# coding:utf-8

import _env
import lib.io_poll as io_poll
import unittest
import os
import sys
import threading

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
        ev1 = threading.Event ()
        ev2 = threading.Event ()
        def __cb1 ():
            print "cb1"
            ev1.set ()
            return
        def __cb2 ():
            print "cb2"
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
        self.assert_ (ev2.is_set ())
        os.close (rd)




    def test_epoll (self):
        ep = io_poll.Poll()
        self._test_1 (ep)
        self._test_2 (ep)

    def test_poll (self):
        p = io_poll.Poll()
        self._test_1 (p)
        self._test_2 (p)

if __name__ == '__main__':
    unittest.main ()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :

