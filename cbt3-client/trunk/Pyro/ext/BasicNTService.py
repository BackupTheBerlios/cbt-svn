#############################################################################
#
#	$Id: BasicNTService.py,v 1.3 2004/05/23 21:48:23 irmen Exp $
#	An NT service that runs the Pyro Name Server
#   Author: Syver Enstad  syver-en@online.no
#
#	This is part of "Pyro" - Python Remote Objects
#	Which is (c) Irmen de Jong - irmen@users.sourceforge.net
#
#############################################################################

import sys
import win32serviceutil
import threading
import win32service
import win32api
import win32con


class BasicNTService(win32serviceutil.ServiceFramework, object):
	""" Abstract base to help out with building NT services
	in Python with the win32all(by Mark Hammond) support for
	python nt services.

	Remember to set the two following class attributes
	to something sensible in your subclass
	_svc_name_ = 'PyroNS'
	_svc_display_name_ = 'Pyro Naming Service NT service'

	The following are optional
	 _svc_deps_: This should be set to the list of service names
				 That need to be started before this one.
	 _exe_name_: This should be set to a service .EXE if you're not
				 going to use PythonService.exe
	 _svc_description_ : This is the descriptive string that you find
						 in the services applet

	To register the service with the SCM the easiest way is to include the
	following at the bottom of the file where your subclass is defined.
	if __name__ == '__main__':
		TheClassYouDerivedFromBasicNTService.HandleCommandLine()

	"""
	def __init__(self, args):
		# PythonService.exe is a special executable that hosts Python programs
		# running as Windows NT services.  Python programs running as NT
		# services must not send output to the default sys.stdout or sys.stderr
		# streams, because those streams are not fully functional in the NT
		# service execution environment; sending output to them will eventually
		# cause an IOError ("Bad file descriptor").  This problem can be
		# overcome by replacing the default system streams with a stream that
		# discards any data passed to it (like redirection to /dev/null on
		# Unix).
		#   Unlike the normal python.exe, PythonService.exe provides a support
		# module named 'servicemanager', so by attempting to import the
		# servicemanager module, we can determine whether this program is
		# "running as a service" or "running as a normal program".
		#   A further subtlety is that PythonService.exe is capable of hosting
		# services in debug mode, which provides fully functional system output
		# streams and an attached console window.
		try:
			import servicemanager # Hosted by PythonService.exe?
			if not servicemanager.Debugging(): # Not running in debug mode?
				sys.stdout = sys.stderr = open('nul', 'w') # Redirect.
		except ImportError:
			# The servicemanager module is not available, which means this
			# program is not hosted by PythonService.exe, so there's no problem
			# with the system output streams.
			pass

		win32serviceutil.ServiceFramework.__init__(self, args)
		self._stopEvent = threading.Event()

	def SvcStop(self):
		""" Template method from win32serviceutil.ServiceFramework"""
		# first tell SCM that we have started the stopping process
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		self._stopEvent.set()

	def _shouldStop(self):
		return self._stopEvent.isSet()

	def _doRun(self):
		raise NotImplementedError

	def _doStop(self):
		raise NotImplementedError

	def SvcDoRun(self):
		""" part of Template method SvcRun
		from win32serviceutil.ServiceFramework"""
		self.logStarted()
		self._doRun()
		self._stopEvent.wait()
		self._doStop()
		self.logTermination()
		return 0

	def logTermination(self):
		import servicemanager
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
									  servicemanager.PYS_SERVICE_STOPPED,
									   (self._svc_name_, ""))
		
	def logStarted(self):
		import servicemanager
		servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
							  servicemanager.PYS_SERVICE_STARTED,
							  (self._svc_name_, ''))	 

	def CustomOptionHandler(cls, opts):
		#out=open("c:\\log.txt","w")
		print "Installing the Pyro %s" % cls._svc_name_
		args = raw_input("Enter command line arguments for %s: " % cls._svc_name_)
		try:
			createRegistryParameters(cls._svc_name_, args.strip())
		except Exception,x:
			print "Error occured when setting command line args in the registry: ",x
		try:
			cls._svc_description_
		except LookupError:
			return

		key = win32api.RegCreateKey(win32con.HKEY_LOCAL_MACHINE,
			"System\\CurrentControlSet\\Services\\%s" % cls._svc_name_)
		try:
			win32api.RegSetValueEx(key, "Description", 0, win32con.REG_SZ, cls._svc_description_);
		finally:
			win32api.RegCloseKey(key)
	CustomOptionHandler = classmethod(CustomOptionHandler)


	def HandleCommandLine(cls):
		import sys
		if win32serviceutil.HandleCommandLine(cls, customOptionHandler=cls.CustomOptionHandler) != 0:
		    return     # some error occured
		if sys.argv[1] in ("install", "update"):
			print "\nYou can configure the command line arguments in the Registry."
			print "The key is: HKLM\\System\\CurrentControlSet\\Services\\%s" % cls._svc_name_
			print "The value under that key is:  ", pyroArgsRegkeyName
			args=getRegistryParameters(cls._svc_name_)
			if args is not None:
				print "(it is currently set to:  '%s')" % args
			else:
				print "(it is currently not set)"
			print 
	HandleCommandLine = classmethod(HandleCommandLine)



pyroArgsRegkeyName = "PyroServiceArguments"


def getRegistryParameters(servicename):
    key=win32api.RegOpenKey(win32con.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Services\\"+servicename)
    try:
        try:
            (commandLine, regtype) = win32api.RegQueryValueEx(key,pyroArgsRegkeyName)
            return commandLine
        except:
            pass
    finally:
        key.Close()
        
    createRegistryParameters(servicename, pyroArgsRegkeyName, "")
    return ""


def createRegistryParameters(servicename, parameters):
    newkey=win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Services\\"+servicename,0,win32con.KEY_ALL_ACCESS)
    try:
        win32api.RegSetValueEx(newkey, pyroArgsRegkeyName, 0, win32con.REG_SZ, parameters)
    finally:
        newkey.Close()
