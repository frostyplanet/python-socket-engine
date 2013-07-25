#!/usr/bin/env python
# coding:utf-8

import _env
import lib.coro_engine as bluelet
from lib.coro_engine import CoroEngine
import unittest

class TestCoro(unittest.TestCase):

    def run_test(self, func):
        engine = CoroEngine()
        engine.run(func) 
        engine.loop()



class TestDelegator(TestCoro):

    def test_1(self):
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

        self.run_test(parent())
        print "test_1 done"
   
    def test_exception(self):
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
        self.run_test(exc_grandparent())
        print "test_2 done"

    def test_exception_2_level(self):
        def child():
            print "ch"
            yield 
            raise Exception("child error")
        def parent():
            print "p"
            try:
                yield child()
            except Exception, e:
                print "parent caught", e
                yield bluelet.end(1)
            return
        def grandparent():
            try:
                print "g"
                res = yield parent()
                assert res == 1
            except:
                self.fail("impossible")
        self.run_test(grandparent())
    
    def test3(self):
        def exc_child():
            yield bluelet.null()
        def parent():
            for i in xrange(10000):
#                yield exc_child()
                yield bluelet.spawn(exc_child())
        self.run_test(parent())
        print "test_3 done"

if __name__ == '__main__':
    unittest.main()


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
