synchronous/blocking
threaded/multi-process
asynchronous by polling
asynchronous by callback
asynchronous by event
client and server buffer issues

In this setup the client will be sending work packets in which the server will
perform an operation on and then send back the finished packet. In a real world
situation the client might do additional work such as storing the finished packet
but in our examples they will simply be printed to the screen and discarded.

You should never call _send_ directory on the socket. You should always use the
SocketBase methods to send data since it will transform it into the correct 
format. Also, the latency and throughput simulation will be subverted if you
call send directly on a socket. We use the latency and throughput limit to simulate
slow links and show how an asynchronous client can improve performance when
latency is an issue and not the CPU.

BLOCKING CLIENT AND BLOCKING SERVER
	python3 scss.py

THREADED CLIENT AND BLOCKING SERVER
	python3 tcss.py
	
	This uses a thread for each request. This could be a useful situation
	if you have a very complex work to be done on each request and you are
	unable to break it up. You will not gain any performance increase from
	multiple processors since the GIL (global interpretor lock) in Python
	will mostly prevent threads from running at the same time.

ASYNCHRONOUS POLLING CLIENT AND BLOCKING SERVER
	python3 apcss.py
	
	This creates requests and polls for them. The amount
	of CPU burned increases as the number of requests in
	wait increases. See the callback example below for how
	to eliminate this problem.
	
ASYNCHRONOUS CALLBACK CLIENT AND BLOCKING SERVER
	python3 accss.py
	
	This is similar to the asynchronous polling client except we do
	not poll for individual items which makes polling consume a
	constant amount of CPU time instead of it increasing with the
	number of items.