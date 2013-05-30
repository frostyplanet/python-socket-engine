#!/usr/bin/env python
# coding:utf-8

import _env
import lib.coro_engine as bluelet
from lib.coro_engine import CoroEngine
import unittest

class TestCoro (unittest.TestCase):

    def run_test (self, func):
        engine = CoroEngine ()
        engine.run (func) 
        engine.loop ()



class TestDelegator (TestCoro):

    def test_1 (self):
        def child():
            print 'Child started.'
            yield bluelet.null()
            print 'Child resumed.'
            yield bluelet.null()
            print 'Child ending.'
            yield bluelet.end(42)

        def parent():
            print 'Parent started.'
            yield bluelet.null()
            print 'Parent resumed.'
            result = yield child()
            print 'Child returned:', repr(result)
            print 'Parent ending.'

        self.run_test (parent())
        print "test_1 done"
    
    def test2 (self):
        def exc_child():
            yield bluelet.null()
            raise Exception()
        def exc_parent():
            try:
                yield exc_child()
            except Exception, exc:
                print 'Parent caught:', repr(exc)
        def exc_grandparent():
            yield bluelet.spawn(exc_parent())
        self.run_test (exc_grandparent())
        print "test_2 done"



if __name__ == '__main__':
    unittest.main ()


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
