import os, time, shutil, threading
import Queue
import jabber
from jabber_connection import JabberConnection

DEBUG_LEVEL = 1

class CbtJabber:
	
	def __init__(self, account):
		
		self.roster = {}
		self.account = account
		
		self.msgQueue = Queue.Queue()
		self.rosterQueue = Queue.Queue()
		
		try:
			self.jabberConnection = JabberConnection(self, self.account)
			self.thread = threading.Thread(target = self.jabberConnection.spinMyWheels)
			self.thread.setDaemon(1)
			self.thread.start()
		except:
			pass

if __name__ == "__main__":
	account = {"server": "localhost", "username": "wrepsz", "password":"delike", "resource":"cbt"}
	CbtJabber(account)

	while 1:
		pass
