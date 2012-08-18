python-socket-engine
====================

by frostyplanet at gmail.com

async / sync socket framework

Features:

* pure python, no third party cpython module is required. tested for python >= 2.3.4  

* listen & unlisten for multiple socket for different use 

* with replacable backends:  select.poll, select.epoll (python2.6+) or python-epoll.

* read_unblock, write_unblock, readline_unblock, connect_unblock is implemented for aync nonblocking mode.

* GIL friendly, so you can use it to create your threaded server or threaded-pool server as you want

* optional timeout for nonblocking mode (in seconds)

* optional inactive connection checking (idle timeout, in seconds)

* optional new connection callback to filter out unauthorized connection

* optional debug stack trace for aync calls

Core components:  

  socket_engine.py  (framework)

  io_poll.py     (poll & epoll backends)

  mylist.py  (list wrapper)

Misc:

  async_httphandler.py  (a BaseHTTPServer.py rewrite for async mode to implement a simple http server)

  timecache.py  (cache to save for frequent time.time () calls )

  net_io.py (fixed length header for socket interaction, and safe recvall() & sendall() )


Testing: 

  Onced tested and optimised in 3k+ connection with 2k+ QPS production environment. More tests will be appreciated.

  See test/test_socketengine.py for functional test, and test/test_server.py for async / sync performance tests.

  Syncronized model is about 2x faster than aync model,  due to footprint of callbacks. 
But async model is more cpu friendly with large numbers of connectins.


