If you are here you are here because of one or more of the following reasons:

* want to use threads for network operations
* interested in how you might perform asynchronous operations over the network
* want to send messages across TCP but not sure how
* need a decent library to use over TCP for your client or server

_And, likely many more reasons although those are the major ones I can think of._

A couple of things to get straight off the bat are firstly you will not gain any
performance using threads or asynchronous operations if you are already maximizing
your bandwidth and/or latency is not a problem. Performing multiple operations allows
you to maximum the bandwidth and minimize latency creating I/O wait. Yes, latency
creates a form of I/O blocking since you must wait for a response in many situations
before doing anything else. Instead of simply waiting you can send more requests if
possible and have them being worked on while you wait for them to complete.

_The synchronous client and server are a great example of having lots of work to perform
but being stuck waiting because of network latency. You will notice that it sends a
work message only to be left waiting for it to be sent back before continuing. The other
demonstrations build from this by sending multiple work messages at a time, and you will
notice that they complete much more work in the same amount of time._

In this set up the client will be sending work packets in which the server will
perform an operation on and then send back the finished packet. In a real world
situation the client might do additional work such as storing the finished packet
but in our examples they will simply be printed to the screen and discarded.

You should never call _send_ directly on the socket. You should always use the
SocketBase methods to send data since it will transform it into the correct 
format. Also, the latency and throughput simulation will be subverted if you
call send directly on a socket. We use the latency and throughput limit to simulate
slow links and show how an asynchronous client can improve performance when
latency is an issue and not the CPU.

_See SocketBase.py for additional information about the methods._

_The SocketBase.py has a hard coded value of 2 seconds for the latency, and
the bandwidth is only limited by your loop back network device. If you wish
to use SocketBase in production applications you can actually modify the code
to remove the latency simulation thread. _

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