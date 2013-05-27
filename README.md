python-socket-engine
====================

by frostyplanet at gmail.com

async / sync socket framework based on callbacks

Features
__________

* pure python, no third party cpython module is required. tested for python >= 2.3.4  

* listen multiple port for different callbacks

* with replacable backends:  select.poll, select.epoll (python2.6+) or python-epoll.

* (fix-len)read_unblock, (fix-len)write_unblock, readline_unblock, connect_unblock is implemented for aync nonblocking mode.

* GIL friendly, so you can use it to create your threaded server or threaded-pool server as you want

* optional timeout for nonblocking mode (in seconds)

* optional inactive connection checking (idle timeout, in seconds)

* optional new connection callback to filter out unauthorized connections

* optional debug stack trace for aync calls


Compared to other framework
----------------------------
Before I started this project, I need to write a app to be deployed on thousands machines (running different linux distros and some without internet access),
high parallel network i/o is desired, and better be pure python to minimize deployment effort. While Gevent needs compile c extensions, and asyncore in python lib 
lacks a lot of functionality (there is no fix-len unblocking send/recv, no timeout, etc), so I decided to write it myself. It's event triggered, connect/read/write operation has ok/error callbacks. you can organize the code in closures or functions with suitable arguments.


Core components
----------------

    socket_engine.py  (framework)

	socket_engine_ssl.py (SSL support)

    io_poll.py     (poll & epoll backends)

Extensions & Helper & misc
----------------

    async_httphandler.py  (a BaseHTTPServer.py rewrite for async mode to implement a simple http server)
    
    job_queue.py  (thread-pool job workers)

    rpc.py & rpc_server.py  (a thread-pool rpc server and client implementation using SSL)

    timecache.py  (cache to save for frequent time.time () calls )

    net_io.py (fixed length header for socket interaction, and safe recvall() & sendall() )


Testing
----------------

Onced tested and optimised in 3k+ connection with 2k+ QPS production environment. More tests will be appreciated.

See test/test_socketengine.py for functional test, and test/test_server.py for async / sync performance tests.

With sequenced 100k read & write, async model is as fast as sync model, and async model is capable of more throughput, and cpu friendly with large numbers of connectins.

localhost performance testing in test/test_server.py:
  	
testing parameters:

intel i3-2310M (HT off)

each client: 100k sequenced send & recv x 50000 round;

blocking-mode client: 4 client in 4 thread;

unblock-mode client:  4 client multiplex in 1 thread;

blocking-mode server & unblock-mode server both using 1 thread;

result:

blocking-mode client, unblock-mode server,  time: 18.5491240025

blocking-mode clinet, blocking-mode server, time: 19.9843790531

unblock-mode client, unblocking-mode server, time: 25.2030720711

unblock-mode client, block-mode server, time:  26.1123259068

Related projects depend on this framework
----------------

https://github.com/frostyplanet/transwarp

