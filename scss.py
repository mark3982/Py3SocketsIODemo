'''
	scss - synchronous client and synchronous server
	
	This demonstrates a synchronous client and synchronous server. Because
	the server is synchronous it can only handle one client at a time. It
	is unable to work on multiple clients at the same time.	
	
	The client generates work message which are sent to the server. The
	server performs a simple operation on the message to simulate something
	that might happen in the real world. The result is sent back to the client
	which then displays it to the screen.
	
	This code uses LAYER 2 methods from SocketBase.
'''
import socket
import threading
import time
import random

from SocketBase import SocketBase

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
	
def ClientEntry(port):
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
	
	# enter into work loop
	while True:
		# create work
		work = []
		for x in range(0, 10):
			work.append(ord('A') + random.randint(0, 25))
		work = bytes(work)
	
		# send message for server to process
		c.sendMessage2(work)

		try:
			data = c.sock.recv(1024)
		except socket.error as e:
			# connection is dead
			print('connection dead')
			break
			
		if len(data) == 0:
			# connection is dead
			print('connection dead')
			break
		
		for msg in c.getAllMessages2(data):
			print('finished', msg)

		

def ServerEntry(port):
	s = Server('127.0.0.1', port)
	
	st = time.time()
	bi = 0
	
	while True:
		cs = s.accept()[0]
		c = ServerClient(cs)
		while True:
			try:
				data = cs.recv(4096)
				if len(data) == 0:
					# connection is dead
					break
				bi = bi + len(data)
			except socket.error:
				# connection is dead
				break
			
			# send any pending data
			c.send1()
			
			# let client handle data
			for msg in c.getAllMessages2(data):
				# work on message
				msg = c.doWork(msg)
				# send message back
				c.sendMessage2(msg)
			
	
def main():
	port = 4534
	c = threading.Thread(target = ClientEntry, args = (port,))
	s = threading.Thread(target = ServerEntry, args = (port,))
	
	s.start()
	c.start()
	
	s.join()
	c.join()
	
main()