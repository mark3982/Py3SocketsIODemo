'''
	scss - synchronous client and synchronous server
	
	This demonstrates a synchronous client and synchronous server. Because
	the server is synchronous it can only handle one client at a time. It
	is unable to work on multiple clients at the same time.	
	
	The client generates work message which are sent to the server. The
	server performs a simple operation on the message to simulate something
	that might happen in the real world. The result is sent back to the client
	which then displays it to the screen.
'''
import socket
import threading
import time
import random

from SocketBase import SocketBase
from SocketBase import IOMode

class Client(SocketBase):
	def __init__(self, host, port):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		super().__init__(self.sock)
		self.host = host
		self.port = port
	
	def connect(self):
		self.sock.connect((self.host, self.port))
		
class Server:
	def __init__(self, iface, port):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.bind((iface, port))
		self.sock.listen(1)

	def accept(self):
		return self.sock.accept()
			
class ServerClient(SocketBase):
	def __init__(self, sock):
		super().__init__(sock)
	
	def doWork(self, data):
		out = []
		for x in range(0, len(data)):
			out.append(data[x] + 1)
		return bytes(out)
	
def ClientWorkThread(c, work):
	v, rv, work = c.sendVectorMessageWithMode4(work, mode = IOMode.Block)
	print('finished', work)

def ClientEntry(port, threadlimit = 1):
	c = Client('localhost', port)
	# keep trying to connect until we succeed
	while True:
		try:
			c.connect()
			break
		except socket.error:
			pass
	# we have finally connected
	print('connected')
	
	threads = []
	# enter into work loop
	l = 0
	while True:
		# put a limit on the number of threads
		if len(threads) < threadlimit:
			# create work
			work = []
			for x in range(0, 1):
				work.append(ord('A') + random.randint(0, 25))
				
			# this sort of helps to see the sequence
			work[0] = ord('A') + l
			l = l + 1
			if l > 25:
				l = 0
			
			work = bytes(work)
			
			wt = threading.Thread(target = ClientWorkThread, args = (c, work))
			wt.start()
			threads.append(wt)
		else:
			# wait a bit if too many for them to die so
			# we do not just burn CPU with a loop
			time.sleep(0.1)
		
		# remove dead work threads
		tr = []
		for wt in threads:
			if not wt.isAlive():
				tr.append(wt)
		for r in tr:
			threads.remove(r)
		

def ServerEntry(port):
	s = Server('127.0.0.1', port)
	
	st = time.time()
	bi = 0
	
	while True:
		cs = s.accept()[0]
		c = ServerClient(cs)
		while True:
			data = None
			try:	
				data = cs.recv(4096)
				if len(data) == 0:
					# connection is dead
					break
			except socket.error:
				# connection is dead
				break
			
			# send any pending data
			c.send1()
			
			# let client handle data
			for msg in c.getAllVectorMessages3(data):
				v = msg[0]
				rv = msg[1]
				msg = msg[2]
				# work on message
				msg = c.doWork(msg)
				# send message back (in reply to..)
				c.sendVectorMessage3(msg, rvector = v)
			
	
def main():
	port = 4534
	c = threading.Thread(target = ClientEntry, args = (port, 5))
	s = threading.Thread(target = ServerEntry, args = (port,))
	
	s.start()
	c.start()
	
	s.join()
	c.join()
	
main()