'''
	Asynchronous Callback Client With Synchronous Server
	
	see README.md
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
		self.l = 0
	
	def connect(self):
		self.sock.connect((self.host, self.port))
		
	def createWork(self):
		# create work
		work = []
		for x in range(0, 1):
			work.append(ord('A') + random.randint(0, 25))
			
		# this sort of helps to see the sequence
		work[0] = ord('A') + self.l
		self.l = self.l + 1
		if self.l > 25:
			self.l = 0
		
		work = bytes(work)
		return work
		
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
	
	def __eventWork(argument, vector, rvector, msg):
		print('finish', msg)
		del argument[rvector]
		
	work = {}
	# enter into work loop
	l = 0
	while True:
		if len(work) < threadlimit:
			workitem = c.createWork()
			v = c.sendVectorMessageWithMode4(workitem, mode = IOMode.Callback, callback = (__eventWork, work))
			work[v] = workitem
		else:
			time.sleep(0.1)
			
		# this will read any messages and dispatch the callbacks
		c.handleVectorMessages4(block = False)

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
	print('Asynchronous Callback Client With Synchronous Server')

	port = 4534
	c = threading.Thread(target = ClientEntry, args = (port, 5))
	s = threading.Thread(target = ServerEntry, args = (port,))
	
	s.start()
	c.start()
	
	s.join()
	c.join()
	
main()