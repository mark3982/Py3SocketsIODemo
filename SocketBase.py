'''
	This forms the base communication functions for either a server
	or a client. 
	
	There are four layers. Each layer prepends it's layer number after
	the methods name. This makes it easier to see what layer you are
	using when writing code for learning. You are unable to mix layer
	2 and 3 across the same connection. If you do it will cause problems
	including exceptions and data corruption. Each side must use either
	layer 2 or 3. 
	
	
	The first layer supports raw sending and receiving. We also support 
	an application level buffer for sending. This prevents us from having 
	to block when trying to send a large amount of data. This can happen 
	when we produce a message for example that is larger then the outbound 
	internal socket buffer. If we did not use an application layer buffer 
	we would be forced to block and wait for all the data to be sent. This 
	would prevent us from using an asynchronous or threaded model.
	
		send1(data = None)				- sends data and if unable to send will buffer data
		getOutBufferSize1()				- gets the number of bytes in our application level buffer
		
		The getOutBufferSize can be used to determine if our buffer is getting too large
		and if so we could stop reading incoming data until it drops below. This is used
		to prevent a client or server from sending us too much data causing us to produce
		more data then we can transmit eventually causing us to run out of memory or degrade
		performance to the point we can no longer operation. This could be done intentionally
		by a client (DoS attack) or unintentionally.
		
	
	The second layer provides variable length messages. This allows us to
	send and receive variable length messages instead of a sequence of bytes.
	This layer does not implement a recv method. Instead you must call the
	recv on the socket directly and feed the data into the appropriate methods.
	
		getAllMessages2(data = None) 	- returns a list of all fully received messages
		getMessage2(data = None)			- returns a single received message
		sendMessage2(msg)				- sends a message
		
	The third layer provides unique variable length messages. This means each
	message is tagged with a unique identifier. This forms the basis for asynchronous
	work. Since we can now tell which packet belongs to what producer or consumer.
	
		sendVectorMessage3(msg, rvector = 0)	- returns vector of message
		getAllVectorMessages3(data = None)	- returns a list of tuples (vector, rvector, message)
		getVectorMessage3(data = None)		- returns a tuple of (vector, rvector, message)
		
		When we send a vector message it has two vectors. One of the vectors is
		optional and can be anything. The other vector is generated internally
		and must be unique. The optional vector can be used to tag a message as
		a reply to a previous message.
		
	The forth layer provides support for different I/O modes. This layer provides locking
	
		sendVectorMessageWithMode4(msg, rvector = 0, mode = IOMode.Block, callback = None)
			This will send a vector message using one of four different modes. The Block mode
			will wait for a reply. The Async mode will return but designate the reply to be
			stored when it is received. The Callback mode will execute a callback with an argument
			when the message is received. The Discard mode will no wait for a reply and will
			cause the reply if any to be discarded if received. Using the mode Discard is the same
			as using sendVectorMessage3(msg, rvector).
		
		handleVectorMessages4(msg, rvector = None, block = False)
			This will either check for a reply vector message or receive vector messages. If
			a vector message is received that does not match rvector or rvector is None it 
			will discard, store, or execute the callback. If block is true it will forever
			wait for a specific message, or forever receive messages. It is uncommon to
			use this function to forever receive messages but it is supported.
		
			IOMode.Block				- wait for reply
			IOMode.Async				- do not wait for reply but store reply if received
			IOMode.Callback				- execute callback when reply arrives
			IOMode.Discard				- do not wait for reply and do not store reply when received
		
			The handleVectorMessages4 implements the support for callbacks and stored messages. If
			you have sent a message with the mode Async or Callback this function will either check
			and return a message sent with Async, or execute the callback.	
'''

from io import BytesIO
import collections
import struct
import threading
import socket
import select

import time					# used by latency simulation!

class IOMode:
	Block 			= 0
	Async			= 1
	Callback		= 2
	Discard			= 3

class ConnectionLostException(Exception):
	pass
	
class SocketBase():
	def __init__(self, sock):
		self.sock = sock
		self.inbuf = BytesIO()
		self.inbuf_cursz = None
		self.oubuf = collections.deque()
		self.oubufsz = 0
		self.vector = 0
		
		self.keepresult = {}
		self.callback = {}
		
		self.socklock = threading.RLock()
		self.vectorlock = threading.RLock()
		
		# LATENCY SIMULATION THREAD
		self.slow = []
		self.slowsz = 0
		self.slowlock = threading.Lock()
		self.__lst = threading.Thread(target = SocketBase.__latencySimThread, args = (self,))
		self.__lst.start()
		
	'''
		This is a work horse for both threaded and asynchronous modes.
		
		1. can check for a message having arrived (Async)
		2. can receive messages and execute callbacks (Callback)
		3. can block for a specific message (Block)
		4. can receive and discard messages (Discard)
		
		You can poll for an Async message, or block for one.
	'''
	def handleVectorMessages4(self, rvector = None, block = True):
		# someone may have beat us here.. so check for message.. only check
		# if it has been signaled to be stored.. otherwise what/why are we
		# waiting for?
		release = False
		if rvector is not None and rvector in self.keepresult:
			# polling! (callback could be more efficient)
			while not self.socklock.acquire(False):
				if self.keepresult[rvector] is not None:
					ret = self.keepresult[rvector]
					del self.keepresult[rvector]
					return ret
				time.sleep(0.01)
			release = True
	
		# grab a lock
		with self.socklock:
			# it could have been placed into the list between right before or after we checked for it
			# but before we acquired the lock so now that we hold the lock we can be sure nothing
			# will change `keepresult`.. so lets do a final check
			if rvector is not None and rvector in self.keepresult and self.keepresult[rvector] is not None:
				ret = self.keepresult[rvector]
				del self.keepresult[rvector]
				return ret
		
			# compensate for the fact that we already ended up locking
			# the lock.. which i thought was better than releasing and
			# then trying to lock again
			if release:
				self.socklock.release()
		
			while True:
				# wait on data
				if block:
					timeout = None
				else:
					timeout = 0
				
				# only check if can write if we have data to send
				if self.getOutBufferSize1() > 0:
					w = [self.sock]
				else:
					w = []
				
				# check for readable, writeable, and exceptions
				r, w, e = select.select([self.sock], w, [self.sock], timeout)
				
				if e:
					# it could be OOB.. but we do not support that
					raise ConnectionLostException()
				
				# read any data
				data = None
				if r:
					try:
						data = self.sock.recv(4096)
						if len(data) == 0:
							raise ConnectionLostException()
					except:
						data = None
				
				# empty buffers if any...
				if w:
					self.send1(block = False)
				
				ret = None
				for msg in self.getAllVectorMessages3(data):
					# process messages
					v = msg[0]
					rv = msg[1]
					msg = msg[2]
				
					# save this..
					if rv == rvector:
						ret = (v, rv, msg)
						continue
					
					# just store it (memory leak warning)
					if rv in self.keepresult:
						self.keepresult[rv] = (v, rv, msg)
						continue
						
					# execute callback
					if rv in self.callback:
						cb = self.callback[rv]
						del self.callback[rv]
						cb[0](cb[1], v, rv, msg)
						continue
				
				# we found it so return with it
				if ret is not None:
					return ret
				
				# exit
				if block is False:
					break
		
	def sendVectorMessageWithMode4(self, msg, rvector = 0, mode = IOMode.Block, callback = None):
		# see IOMode.Async explanation
		vector = self.vector
		
		if mode == IOMode.Async:
			# we have to set this before we sent due to the possibility
			# of another thread receiving messages and it messages making
			# it here before this is set
			self.keepresult[vector] = None
			return self.sendVectorMessage3(msg, rvector)
		
		if mode == IOMode.Callback:
			if callback is None:
				raise Exception('If mode is specified callback, then callback argument must be specified.')
			# see IOMode.Async explanation
			self.callback[vector] = callback
			return self.sendVectorMessage3(msg, rvector)
		
		if mode == IOMode.Discard:
			return self.sendVectorMessage3(msg, rvector)
		
		# a little helpful debugging exception..
		if mode != IOMode.Block:
			raise Exception('The mode specified is unknown. [%s]' % mode)
		
		self.keepresult[vector] = None
		self.sendVectorMessage3(msg, rvector, block = False)
		
		# this will either return immediately because some other thread
		# has already serviced the message or it will block until the
		# message arrives
		return self.handleVectorMessages4(rvector = vector, block = True)
		
	
	def sendVectorMessage3(self, msg, rvector = 0, block = True):
		# if we do not lock two threads could get the same vector
		# value, or not increment the vector value either way it
		# would cause crazy bugs that would be difficult to trace
		# down..
		with self.vectorlock:
			self.sendMessage2(struct.pack('>QQ', self.vector, rvector) + msg, block = block)
			vector = self.vector
			self.vector = self.vector + 1
			return vector
	
	def getAllVectorMessages3(self, data = None):
		msgs = []
		while True:
			msg = self.getVectorMessage3(data)
			if msg is None:
				return msgs
			data = None
			msgs.append(msg)
		return msgs
		
	def getVectorMessage3(self, data = None):
		msg = self.getMessage2(data)
		if msg is None:
			return None
		# break out vector components
		hdrsz = struct.calcsize('>QQ')
		vector, rvector = struct.unpack_from('>QQ', msg)
		msg = msg[hdrsz:]
		return (vector, rvector, msg)
		
	
	def getAllMessages2(self, data = None):
		msgs = []
		while True:
			msg = self.getMessage2(data)
			if msg is None:
				return msgs
			data = None
			msgs.append(msg)
	
	def sendMessage2(self, msg, block = True):
		self.send1(struct.pack('>I', len(msg)) + msg, block = block)
		
	def getOutBufferSize1(self):
		return self.oubufsz
		
	###################################################
	############## LATENCY SIMULATION #################
	###################################################
	# this is started as a thread and is meant to be
	# invisible to someone using this class
	def __latencySimThread(self):
		while True:
			with self.slowlock:
				tr = []
				for item in self.slow:
					if time.time() - item[0] > 2:
						# append to right side (end of list)
						self.oubuf.append(item[1])
						self.oubufsz = self.oubufsz + len(item[1])
						self.slowsz = self.slowsz - len(item[1])
						tr.append(item)
						
				for item in tr:
					self.slow.remove(item)
			# just check if data can be sent instead of having
			# to grab the lock and try to iterate list
			if self.getOutBufferSize1() > 0:
				self.__send1(None, False)
			time.sleep(0.1)
	####################################################
	
	# if you want to skip the latency simulation you can change the names
	# of these functions and call __send1 instead...
	def send1(self, data = None, block = False):
		###################################################
		############## LATENCY SIMULATION #################
		###################################################
		# normally these would be placed directly into
		# the self.oubuf list, but we let another thread
		# do that to simulate latency...
		with self.slowlock:
			if data is not None:
				# add to slow list
				self.slowsz = self.slowsz + len(data)
				self.slow.append((time.time(), data))
				return
		###################################################
	
	def __send1(self, data = None, block = False):
		if block is False:
			block = 0
		if block is True:
			block = None
		# this lock prevents multiple threads from trying
		# to send things at the same time..
		with self.socklock and self.slowlock:
			# i keep the old value around because since we support
			# blocking and non-blocking we need to kinda restore it
			# once we are done using it
			old = self.sock.gettimeout()
			
			self.sock.settimeout(block)
			
			# try to send data
			while len(self.oubuf) > 0:
				data = self.oubuf.popleft()
				totalsent = 0
				while totalsent < len(data):
					sent = 0
					try:
						sent = self.sock.send(data[totalsent:])
					except socket.error:
						# problem.. place remaining back into buffer
						self.oubuf.appendleft(data[totalsent:])
						self.oubufsz = self.oubufsz - totalsent
						self.sock.settimeout(old)
						return
					if sent == 0:
						# problem.. place remaining back into buffer
						self.oubuf.appendleft(data[totalsent:])
						self.oubufsz = self.oubufsz - totalsent
						self.sock.settimeout(old)
						return
					totalsent = totalsent + sent
				# adjust for total sent out
				self.oubufsz = self.oubufsz - totalsent
			# everything has been sent
			self.sock.settimeout(old)
		return
		
	def getMessage2(self, data = None):
		# we do not want multiple threads inside this
		# block at the same time unless you want really
		# weird results..
		with self.socklock:
			hdrsz = struct.calcsize('>I')
			if data is not None:
				self.inbuf.write(data)
			
			# are we reading the header or the data?
			if self.inbuf_cursz is None:
				# do we have enough to read the header?
				if self.inbuf.tell() > hdrsz:
					# seek to beginning of stream
					self.inbuf.seek(0)
					sz = struct.unpack('>I', self.inbuf.read(hdrsz))[0]
					self.inbuf_cursz = sz
					# seek to end of stream
					self.inbuf.seek(0, 2)
				if self.inbuf_cursz is None:
					return None

			if (self.inbuf.tell() - hdrsz) >= self.inbuf_cursz:
				self.inbuf.seek(hdrsz)
				rdata = self.inbuf.read(self.inbuf_cursz)
				# place remaining data into buffer removing what we have read out
				data = self.inbuf.read()
				self.inbuf = BytesIO()
				self.inbuf.write(data)
				self.inbuf_cursz = None
				return rdata
		return None