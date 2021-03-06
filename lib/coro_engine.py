#!/usr/bin/env python
# coding:utf-8


"""

CoroEngine: inspired by and rewrite from Bluelet, to incoperate coro with a event engine

by frostyplanet@gmail.com

tribute should be given to author(s) of Bluelet

"""
import socket
import select
import sys
import types
import errno
import traceback
import time
import collections


# A little bit of "six" (Python 2/3 compatibility): cope with PEP 3109 syntax
# changes.

PY3 = sys.version_info[0] == 3
if PY3:
    def _reraise(typ, exc, tb):
        raise exc.with_traceback(tb)
else:
    exec("""
def _reraise(typ, exc, tb):
    raise typ, exc, tb
    """)

def reraise(exc_info):
    _reraise(exc_info[0], exc_info[1], exc_info[2])

# Basic events used for thread scheduling.

class Event(object):
    """Just a base class identifying Bluelet events. An event is an
    object yielded from a Bluelet thread coroutine to suspend operation
    and communicate with the scheduler.
    """

    def proc(self, engine, coro):
        pass


class WaitableEvent(Event):
    """A waitable event is one encapsulating an action that can be
    waited for using a select() call. That is, it's an event with an
    associated file descriptor.
    """
    def __init__(self):
        self.ret = None
        self.error = None
        self.done = False

    def waitables(self):
        """Return "waitable" objects to pass to select(). Should return
        three iterables for input readiness, output readiness, and
        exceptional conditions(i.e., the three lists passed to
        select()).
        """
        return(), (), ()

    def fire(self):
        pass

class EngineEvent(WaitableEvent):

    def fire(self):
        if self.error is not None:
            raise self.error
        return self.ret


class ValueEvent(Event):
    """An event that does nothing but return a fixed value."""
    def __init__(self, value):
        self.value = value

    def proc(self, engine, coro):
        engine.advance_thread(coro, self.value)

#class ExceptionEvent(Event):
#    """Raise an exception at the yield point. Used internally."""
#    def __init__(self, exc_info):
#        self.exc_info = exc_info

class SpawnEvent(Event):
    """Add a new coroutine thread to the scheduler."""
    def __init__(self, coro):
        self.spawned = coro

#    def proc(self, engine, coro):
#        engine.threads[self.spawned] = ValueEvent(None)  # Spawn.
#        return True
#        engine.poll()
#        engine.advance_thread(coro, None)
#        engine.advance_thread(self.spawned, None)


class JoinEvent(Event):
    """Suspend the thread until the specified child thread has
    completed.
    """
    def __init__(self, child):
        self.child = child

    def proc(self, engine, coro):
        engine.threads[coro] = SUSPENDED  # Suspend.
        engine.joiners[self.child].append(coro)

#class KillEvent(Event):
#    """Unschedule a child thread."""
#    def __init__(self, child):
#        self.child = child
#
#    def proc(self, engine, coro):
#        self.kill_thread(self.child)
#        return True

#class DelegationEvent(Event):
#    """Suspend execution of the current thread, start a new thread and,
#    once the child thread finished, return control to the parent
#    thread.
#    """
#    def __init__(self, coro):
#        self.spawned = coro

class ReturnEvent(Event):
    """Return a value the current thread's delegator at the point of
    delegation. Ends the current(delegate) thread.
    """
    def __init__(self, value):
        self.value = value

    def proc(self, engine, coro):
        engine.complete_thread(coro, self.value)


#class SleepEvent(WaitableEvent):
#    """Suspend the thread for a given duration.
#    """
#    def __init__(self, duration):
#        self.wakeup_time = time.time() + duration
#
#    def time_left(self):
#        return max(self.wakeup_time - time.time(), 0.0)


class ThreadException(Exception):
    def __init__(self, coro, exc_info):
        self.coro = coro
        self.exc_info = exc_info
    def reraise(self):
        _reraise(self.exc_info[0], self.exc_info[1], self.exc_info[2])

SUSPENDED = Event()  # Special sentinel placeholder for suspended threads.

class Delegated(Event):
    """Placeholder indicating that a thread has delegated execution to a
    different thread.
    """
    def __init__(self, child):
        self.child = child

       
# Public interface for threads; each returns an event object that
# can immediately be "yield"ed.

def null():
    """Event: yield to the scheduler without doing anything special.
    """
    return ValueEvent(None)

def spawn(coro):
    """Event: add another coroutine to the scheduler. Both the parent
    and child coroutines run concurrently.
    """
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return SpawnEvent(coro)

def call(coro):
    """Event: delegate to another coroutine. The current coroutine
    is resumed once the sub-coroutine finishes. If the sub-coroutine
    returns a value using end(), then this event returns that value.
    """
    if not isinstance(coro, types.GeneratorType):
        raise ValueError('%s is not a coroutine' % str(coro))
    return coro
#    return DelegationEvent(coro)

def end(value = None):
    """Event: ends the coroutine and returns a value to its
    delegator.
    """
    return ReturnEvent(value)

#def sleep(duration):
#    """Event: suspend the thread for ``duration`` seconds.
#    """
#    return SleepEvent(duration)

def join(coro):
    """Suspend the thread until another, previously `spawn`ed thread
    completes.
    """
    return JoinEvent(coro)

#def kill(coro):
#    """Halt the execution of a different `spawn`ed thread.
#    """
#    return KillEvent(coro)

 

class CoroEngine():

    MAX_CONCURRENT = 500

    def __init__(self):
        self.threads = {}
        self.pending_threads = []
        # Maps child coroutines to delegating parents.
        self.delegators = {}
        self.event2coro = {}

        # Maps child coroutines to joining(exit-waiting) parents.
        self.joiners = collections.defaultdict(list)

#        self._waitables = []  # TODO  process WaitableEvent
#        self._unknown_waitables = dict()
        self.have_ready = True

    def complete_thread(self, coro, return_value):
        """Remove a coroutine from the scheduling pool, awaking
        delegators and joiners as necessary and returning the specified
        value to any delegating parent.
        """
        try:
            del self.threads[coro]
        except KeyError:
            pass

        if self.threads:
            # Resume delegator.
            if self.delegators and coro in self.delegators:
                self.threads[self.delegators[coro]] = ValueEvent(return_value)
                del self.delegators[coro]

        # Resume joiners.
        if self.joiners and coro in self.joiners:
            for parent in self.joiners[coro]:
                self.threads[parent] = ValueEvent(None)
            del self.joiners[coro]


    def advance_thread(self, coro, value, is_exc=False):
        """After an event is fired, run a given coroutine associated with
        it in the threads dict until it yields again. If the coroutine
        exits, then the thread is removed from the pool. If the coroutine
        raises an exception, it is reraised in a ThreadException. If
        is_exc is True, then the value must be an exc_info tuple and the
        exception is thrown into the coroutine.
        """
        while True:
            try:
                if is_exc:
                    event = coro.throw(*value)
                    is_exc = False
                else:
                    event = coro.send(value)
            except StopIteration:
                self.complete_thread(coro, None)
                return
            except Exception, e:
                if is_exc:
                    reraise(sys.exc_info())
                else:
                    # Thread raised some other exception.
                    self.handle_exception(coro, sys.exc_info())
                return
            if isinstance(event, EngineEvent):
                if event.done:
#                    self.resume_from_waitable(event, coro)
                    if event.error is not None:
                        #throw exception
                        self.advance_thread(coro, (type(event.error), event.error, None), is_exc=True)
                    else:
                        value = event.ret
                        continue
                    #don't have to wait
                else:
                    self.event2coro[event] = coro
                    self.threads[coro] = event  # suspends the coro until resume
                return
            elif isinstance(event, types.GeneratorType):
                # Automatically invoke sub-coroutines. (Shorthand for
                # explicit bluelet.call().)
                self.threads[coro] = Delegated(event)  # Suspend.
                self.threads[event] = ValueEvent(None)  # Spawn.
                self.delegators[event] = coro
                coro = event
                value = None
                continue
                #self.advance_thread(event, None)
                #return
            elif isinstance(event, ValueEvent):
                #self.advance_thread(coro, event.value)
                value = event.value
                continue
            elif isinstance(event, SpawnEvent):
                self.threads[coro] = ValueEvent(None)
                self.threads[event.spawned] = ValueEvent(None)  # Spawn.
                value = None
                continue
            elif isinstance(event, Event):
                self.threads[coro] = event
                val = event.proc(self, coro)
                if val is None:
                    return
                if val == True:
                    value = None
                else:
                    value = val
                continue



    def handle_exception(self, coro, exc_info):

        if coro in self.delegators:
            # The thread is a delegate. Raise exception in its
            # delegator.
            parent = self.delegators[coro]
            del self.delegators[coro]
            del self.threads[coro]
#            self.threads[parent] = event
            self.advance_thread(parent, exc_info, True)
        else:
            self.advance_thread(coro, exc_info, True)
            # The thread is root-level. Raise in client code.
#            if self.threads.get(coro) != event:
#            else:
            #print self.threads, sys.exc_info()

            #self.threads[coro] = event

            
    def kill_thread(self, coro):
        """Unschedule this thread and its(recursive) delegates.
        """
        # Collect all coroutines in the delegation stack.
        coros = [coro]
        while isinstance(self.threads[coro], Delegated):
            coro = self.threads[coro].child
            coros.append(coro)

        # Complete each coroutine from the top to the bottom of the
        # stack.
        for coro in reversed(coros):
            self.complete_thread(coro, None)


    def run(self, coro):
#        if len(self.threads) > self.MAX_CONCURRENT:
#            self.pending_threads.append(coro)
#        else:
        self.threads[coro] = None
        self.advance_thread(coro, None)
#        self.poll()

    def loop(self):
        while self.threads:
            self.poll()

    def resume_from_waitable(self, event, coro=None):
        # Run the IO operation, but catch socket errors.
        if not event.done:
            return
        coro = self.event2coro.get(event)
        if not coro:
            return
        #self.have_ready = True
        if event.error is None:
            self.advance_thread(coro, event.ret)
        else:
            #throw exception
            self.advance_thread(coro, (type(event.error), event.error, None), is_exc=True)


    def poll(self):
        # running immediate events until nothing is ready.
#        if not self.threads and self.pending_threads:
#            if len(self.pending_threads) > self.MAX_CONCURRENT:
#                self.threads = dict.fromkeys(self.pending_threads[0:self.MAX_CONCURRENT], None)
#                self.pending_threads = self.pending_threads[self.MAX_CONCURRENT:]
#            else:
#                self.threads = dict.fromkeys(self.pending_threads, None)
#                self.pending_threads = []
        for coro, event in self.threads.items():
            if event is None:
                self.advance_thread(coro, None)
            elif isinstance(event, Event):
                val = event.proc(self, coro)
#            if val is None:
#                continue
#            if val is True:
#                val = None
#            self.advance_thread(coro, val)

#                if isinstance(event, ReturnEvent):
#                    # Thread is done.
#                    self.complete_thread(coro, event.value)
#                    have_ready = True
#                elif isinstance(event, JoinEvent):
#                    self.threads[coro] = SUSPENDED  # Suspend.
#                    self.joiners[event.child].append(coro)
#                    have_ready = True
#                elif isinstance(event, KillEvent):
#                    self.advance_thread(coro, None)
#                    self.kill_thread(event.child)
#                    have_ready = True
            # Only start the select when nothing else is ready.
#            if not have_ready:
#                self.have_ready = False
#                return
#
                

# If we're exiting with an exception, raise it in the client.

 

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
