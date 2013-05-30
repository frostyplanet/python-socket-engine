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


# Basic events used for thread scheduling.

class Event(object):
    """Just a base class identifying Bluelet events. An event is an
    object yielded from a Bluelet thread coroutine to suspend operation
    and communicate with the scheduler.
    """
    pass

class WaitableEvent(Event):
    """A waitable event is one encapsulating an action that can be
    waited for using a select() call. That is, it's an event with an
    associated file descriptor.
    """
    def waitables(self):
        """Return "waitable" objects to pass to select(). Should return
        three iterables for input readiness, output readiness, and
        exceptional conditions (i.e., the three lists passed to
        select()).
        """
        return (), (), ()

    def fire(self):
        """Called when an assoicated file descriptor becomes ready
        (i.e., is returned from a select() call).
        """
        pass

class ValueEvent(Event):
    """An event that does nothing but return a fixed value."""
    def __init__(self, value):
        self.value = value

class ExceptionEvent(Event):
    """Raise an exception at the yield point. Used internally."""
    def __init__(self, exc_info):
        self.exc_info = exc_info

class SpawnEvent(Event):
    """Add a new coroutine thread to the scheduler."""
    def __init__(self, coro):
        self.spawned = coro

class JoinEvent(Event):
    """Suspend the thread until the specified child thread has
    completed.
    """
    def __init__(self, child):
        self.child = child

class KillEvent(Event):
    """Unschedule a child thread."""
    def __init__(self, child):
        self.child = child

class DelegationEvent(Event):
    """Suspend execution of the current thread, start a new thread and,
    once the child thread finished, return control to the parent
    thread.
    """
    def __init__(self, coro):
        self.spawned = coro

class ReturnEvent(Event):
    """Return a value the current thread's delegator at the point of
    delegation. Ends the current (delegate) thread.
    """
    def __init__(self, value):
        self.value = value

class SleepEvent(WaitableEvent):
    """Suspend the thread for a given duration.
    """
    def __init__(self, duration):
        self.wakeup_time = time.time() + duration

    def time_left(self):
        return max(self.wakeup_time - time.time(), 0.0)

class ReadEvent(WaitableEvent):
    """Reads from a file-like object."""
    def __init__(self, fd, bufsize):
        self.fd = fd
        self.bufsize = bufsize

    def waitables(self):
        return (self.fd,), (), ()

    def fire(self):
        return self.fd.read(self.bufsize)

class WriteEvent(WaitableEvent):
    """Writes to a file-like object."""
    def __init__(self, fd, data):
        self.fd = fd
        self.data = data

    def waitable(self):
        return (), (self.fd,), ()

    def fire(self):
        self.fd.write(self.data)


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
    return DelegationEvent(coro)

def end(value = None):
    """Event: ends the coroutine and returns a value to its
    delegator.
    """
    return ReturnEvent(value)

def sleep(duration):
    """Event: suspend the thread for ``duration`` seconds.
    """
    return SleepEvent(duration)

def join(coro):
    """Suspend the thread until another, previously `spawn`ed thread
    completes.
    """
    return JoinEvent(coro)

def kill(coro):
    """Halt the execution of a different `spawn`ed thread.
    """
    return KillEvent(coro)

 

class CoroEngine ():

    def __init__ (self):
        self.threads = {}
        # Maps child coroutines to delegating parents.
        self.delegators = {}
        self.event2coro = {}

        # Maps child coroutines to joining (exit-waiting) parents.
        self.joiners = collections.defaultdict(list)

#        self._waitables = []  # TODO  process WaitableEvent
        self._unknown_waitables = dict ()

    def complete_thread(self, coro, return_value):
        """Remove a coroutine from the scheduling pool, awaking
        delegators and joiners as necessary and returning the specified
        value to any delegating parent.
        """
        del self.threads[coro]

        # Resume delegator.
        if coro in self.delegators:
            self.threads[self.delegators[coro]] = ValueEvent(return_value)
            del self.delegators[coro]

        # Resume joiners.
        if coro in self.joiners:
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
        if is_exc:
            try:
                next_event = coro.throw(*value)
            except StopIteration:
                self.complete_thread(coro, None)
                return
            except:
                exc_info = sys.exc_info ()
                _reraise (exc_info[0], exc_info[1], exc_info[2])
        else:
            try:
                next_event = coro.send(value)
            except StopIteration:
                self.complete_thread(coro, None)
                return
            except Exception, e:
                # Thread raised some other exception.
                self.handle_exception (coro, e)
                return
        if isinstance(next_event, types.GeneratorType):
            # Automatically invoke sub-coroutines. (Shorthand for
            # explicit bluelet.call().)
            next_event = DelegationEvent(next_event)
        elif isinstance(next_event, WaitableEvent):
#                self._waitables.append (next_event)
            self.event2coro[next_event] = coro

        self.threads[coro] = next_event


    def handle_exception (self, coro, e=None):
        del self.threads[coro]
        te = ThreadException(coro, sys.exc_info())
        event = ExceptionEvent(te.exc_info)
        if te.coro in self.delegators:
            # The thread is a delegate. Raise exception in its
            # delegator.
            self.threads[self.delegators[te.coro]] = event
            del self.delegators[te.coro]
        else:
            # The thread is root-level. Raise in client code.
#            if self.threads.get (coro) != event:
#            else:
            #print self.threads, sys.exc_info()
            self.threads[coro] = event

            
    def kill_thread(self, coro):
        """Unschedule this thread and its (recursive) delegates.
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


    def run_coro (self, coro):
        self.threads[coro] = ValueEvent(None)


    def resume_from_waitable (self, event):
        # Run the IO operation, but catch socket errors.
        coro = self.event2coro.get (event)
        if not coro:
            self._unknown_waitables[event] = None
            return
        try:
            value = event.fire()
        except socket.error as exc:
            if isinstance(exc.args, tuple) and \
                    exc.args[0] == errno.EPIPE:
                # Broken pipe. Remote host disconnected.
                pass
            else:
                self.handle_exception(coro, exc)
                return
                #traceback.print_exc()   #TODO ???
        except Exception, e:
            self.handle_exception(coro, e)
            # Abort the coroutine.
#            del self.event2coro[event]
#            self.threads[coro] = ReturnEvent(None)
            return
        del self.event2coro[event]
        self.advance_thread(coro, value)


    def poll (self):
    # Continue advancing threads until root thread exits.
        if not self.threads:
            return
        # Look for events that can be run immediately. Continue
        # running immediate events until nothing is ready.
        while True:
            have_ready = False

            for coro, event in list(self.threads.items()):
                if isinstance(event, SpawnEvent):
                    self.threads[event.spawned] = ValueEvent(None)  # Spawn.
                    self.advance_thread(coro, None)
                    have_ready = True
                elif isinstance(event, ValueEvent):
                    self.advance_thread(coro, event.value)
                    have_ready = True
                elif isinstance(event, ExceptionEvent):
                    self.advance_thread(coro, event.exc_info, True)
                    have_ready = True
                elif isinstance(event, DelegationEvent):
                    self.threads[coro] = Delegated(event.spawned)  # Suspend.
                    self.threads[event.spawned] = ValueEvent(None)  # Spawn.
                    self.delegators[event.spawned] = coro
                    have_ready = True
                elif isinstance(event, ReturnEvent):
                    # Thread is done.
                    self.complete_thread(coro, event.value)
                    have_ready = True
                elif isinstance(event, JoinEvent):
                    self.threads[coro] = SUSPENDED  # Suspend.
                    self.joiners[event.child].append(coro)
                    have_ready = True
                elif isinstance(event, KillEvent):
                    self.threads[coro] = ValueEvent(None)
                    self.kill_thread(event.child)
                    have_ready = True
                elif isinstance(event, WaitableEvent):
                    self.event2coro[event] = coro
                    if self._unknown_waitables.has_key (event):
                        del self._unknown_waitables[event]
                        self.resume_from_waitable (event)

            # Only start the select when nothing else is ready.
            if not have_ready:
                return

                
#        # If any threads still remain, kill them.
#        for coro in self.threads:
#            coro.close()

# If we're exiting with an exception, raise it in the client.

 

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
