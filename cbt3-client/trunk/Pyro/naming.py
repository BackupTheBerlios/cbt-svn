#############################################################################
#
#	$Id: naming.py,v 2.44 2004/02/05 00:42:33 irmen Exp $
#	Pyro Name Server
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@users.sourceforge.net
#
#############################################################################

import sys, os, socket, string, time
import dircache, shutil, SocketServer
import Pyro
import util, errors, core, protocol, constants


if os.name!='java':			# Jython has no errno/select modules
	import errno
	import select
else:
	# fake an errno module
	class Errno: pass
	errno=Errno()
	errno.EEXIST=-1
	errno.EBUSY=-1
	errno.ENOENT=-1
	errno.EISDIR=-1
	errno.ENOTDIR=-1
	

Log = util.Log

#############################################################################
#
# The Pyro NameServer Locator.
# Use a broadcast mechanism to find the broadcast server of the NS which
# can provide us with the URI of the NS.
# Can also perform direct lookup (no broadcast) if the host is specified.
# (in that case, the 'port' argument is the Pyro port, not a broadcast port).
#
#############################################################################

class NameServerLocator:
	def __init__(self, identification=None):
		Pyro.core._checkInit()	# init required
		self.identification=identification

	def sendSysCommand(self,request,host=None,port=None,trace=0,logerrors=1):
		try:
			return self.__sendSysCommand(request, host, port, trace, logerrors, Pyro.constants.NSROLE_PRIMARY)
		except KeyboardInterrupt:
			raise
		except Exception,x:
			if not port:
				# the 'first' name server failed, try the second
				result=self.__sendSysCommand(request, host, port, trace, logerrors, Pyro.constants.NSROLE_SECONDARY)
				# found the second!
				# switch config for first and second
				Pyro.config.PYRO_NS2_HOSTNAME, Pyro.config.PYRO_NS_HOSTNAME = Pyro.config.PYRO_NS_HOSTNAME, Pyro.config.PYRO_NS2_HOSTNAME
				Pyro.config.PYRO_NS2_PORT, Pyro.config.PYRO_NS_PORT = Pyro.config.PYRO_NS_PORT, Pyro.config.PYRO_NS2_PORT
				Pyro.config.PYRO_NS2_BC_PORT, Pyro.config.PYRO_NS_BC_PORT = Pyro.config.PYRO_NS_BC_PORT, Pyro.config.PYRO_NS2_BC_PORT
				return result
			else:
				raise x

	def __sendSysCommand(self,request,host=None,port=None,trace=0,logerrors=1,role=Pyro.constants.NSROLE_PRIMARY):
		HPB={Pyro.constants.NSROLE_PRIMARY: (Pyro.config.PYRO_NS_HOSTNAME, Pyro.config.PYRO_NS_PORT, Pyro.config.PYRO_NS_BC_PORT),
		     Pyro.constants.NSROLE_SECONDARY: (Pyro.config.PYRO_NS2_HOSTNAME, Pyro.config.PYRO_NS2_PORT, Pyro.config.PYRO_NS2_BC_PORT) }
		if not host:
			host=HPB[role][0]
		if not port:
			if not host:
				# select the default broadcast port
				port = HPB[role][2]
			else:
				# select the default port
				port = HPB[role][1]

		# We must discover the location of the name server.
		# Pyro's NS can answer to broadcast requests.
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			if not host:
				# No host specified. Use broadcast mechanism
				if os.name=='java':
					# Jython handling for broadcast addrs
					destination = ('255.255.255.255', port)
				else:
					# regular python broadcast socket
					destination = ('<broadcast>', port)
				if hasattr(socket,'SO_BROADCAST'):
					s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
			else:
				# use direct lookup with PYROLOC: mechanism, no broadcast
				if trace:
					print 'Locator: contacting Pyro Name Server...'
				uri=core.PyroURI(host,constants.NAMESERVER_NAME,port,'PYROLOC')
				prox=core.getProxyForURI(uri)
				prox._setIdentification(self.identification)
				prox.ping()	# force resolving of PYROLOC: uri
				return prox.URI # return resolved uri
			
			if trace:
				print 'Locator: searching Pyro Name Server...'
			for i in range(Pyro.config.PYRO_BC_RETRIES+1):
				s.sendto(request, destination)  # send to Pyro NS's bc port
				if os.name!='java':
					ins,outs,exs = select.select([s],[],[s],Pyro.config.PYRO_BC_TIMEOUT)
				else:
					ins=[s]		# XXX preliminary Jython solution (no select)
				if s in ins:
					reply, fromaddr = s.recvfrom(1000)
					return reply
				if trace and i<Pyro.config.PYRO_BC_RETRIES:
					print 'Locator: retry',i+1
		except socket.error,e:
			if logerrors:
				Log.error('NameServerLocator','network error:',e)
			if trace:
				print 'Locator: network error:',e
		if logerrors:
			Log.error('NameServerLocator','Name Server not responding to broadcast')
		raise errors.PyroError('Name Server not responding')
	
	def detectNS(self,host=None,port=None,trace=0):
		# just try to detect an existing NS. Don't log errors.
		return core.PyroURI(self.sendSysCommand('location',host,port,trace,0))

	def getNS(self,host=None,port=None,trace=0):
		reply = self.sendSysCommand('location',host,port,trace)
		Log.msg('NameServerLocator','Name Server found:',reply)
		ns=NameServerProxy(core.PyroURI(reply),self.identification)
		ns._setIdentification(self.identification)
		return ns


# NOTE: The NameServerProxy class below is hand crafted.
# This is because we want to enforce the default group name on all name
# arguments that are not absolute.
# In doing so, we make sure that each object name is passed as an
# absolute name (from the name space root) too. This is needed because
# the NS has no state and can only process absolute names for each request.
# Also, the PYRO_NS_DEFAULTGROUP configitem is used to expand non-absolute
# names to absolute names. Because this is done in the proxy, each
# client can have its own PYRO_NS_DEFAULTGROUP.

class NameServerProxy:
	def __init__(self,URI,identification=None,noconnect=0):
		self.URI = URI
		self.objectID = URI.objectID
		self.adapter = protocol.getProtocolAdapter(self.URI.protocol)
		self.adapter.setIdentification(identification)
		if noconnect:
			self.adapter.URI=URI.clone()
		else:
			self.adapter.bindToURI(URI)
		self.adapter.setOneway(["_synccall"])
	def _release(self):
		if self.adapter:
			self.adapter.release()
			
	def __remoteinvoc(self, *args):
		try:
			return self.adapter.remoteInvocation(*args)
		except errors.ProtocolError,x:
			# The remote invocation failed. Try to find the NS again.
			Log.warn('NameServerProxy','Name Server communication problem:',x,' URI was:',self.URI)
			Log.msg('NameServerProxy','trying to find NS again...')
			self.URI=NameServerLocator().detectNS()
			self.objectID=self.URI.objectID
			self.adapter.bindToURI(self.URI)
			Log.msg('NameServerProxy','found NS at',self.URI,".... retry call")
			return self.adapter.remoteInvocation(*args)
			
	def ping(self):
		return self.__remoteinvoc('ping',0)
	def resync(self):
		return self.__remoteinvoc('resync',0)
	def register(self,name,URI):
		return self.__remoteinvoc('register',0,_expandName(name),URI)
	def resolve(self,name):
		return self.__remoteinvoc('resolve',0,_expandName(name))
	def flatlist(self):
		return self.__remoteinvoc('flatlist',0)
	def unregister(self,name):
		return self.__remoteinvoc('unregister',0,_expandName(name))
	def createGroup(self,gname):
		return self.__remoteinvoc('createGroup',0,_expandName(gname))
	def deleteGroup(self,gname):
		return self.__remoteinvoc('deleteGroup',0,_expandName(gname))
	def list(self,gname):
		return self.__remoteinvoc('list',0,_expandName(gname))
	def setMeta(self, name, meta):
		return self.__remoteinvoc('setMeta',0,_expandName(name),meta)
	def getMeta(self, name):
		return self.__remoteinvoc('getMeta',0,_expandName(name))
	def fullName(self,name):
		return _expandName(name)
	def _setSystemMeta(self, name, meta):
		return self.__remoteinvoc('_setSystemMeta',0,_expandName(name),meta)
	def _getSystemMeta(self, name):
		return self.__remoteinvoc('_getSystemMeta',0,_expandName(name))
	def _setIdentification(self, ident):
		self.adapter.setIdentification(ident)
	def _resync(self, twinProxy):
		return self.adapter.remoteInvocation('_resync',0,twinProxy)
	def _synccall(self, *args):
		self.adapter.remoteInvocation('_synccall',constants.RIF_Varargs, args)
	def __getstate__(self):
		self._release()		# release socket to be able to pickle this object
		return self.__dict__

# Can be used to expand names to absolute names (NS proxy uses this)
def _expandName(name):
	if Pyro.config.PYRO_NS_DEFAULTGROUP[0]!=':':
		raise errors.NamingError('default group name is not absolute')
	if name:
		if name[0]==':':
			return name
		return Pyro.config.PYRO_NS_DEFAULTGROUP+'.'+name
	else:
		return Pyro.config.PYRO_NS_DEFAULTGROUP


#############################################################################
#
#	The Name Server (a Pyro Object).
#
#	It has more methods than the ones available in the proxy (above)
#	but that is because the other methods are private and for internal
#	use only.
#
#############################################################################


class NameServer(core.ObjBase):
	def __init__(self, role=Pyro.constants.NSROLE_SINGLE):
		core.ObjBase.__init__(self)
		self.root=NamedTree('<root>')
		self.lock=util.getLockObject()
		self.role=role
		self.otherNS=None
		# create default groups
		self.createGroup(':'+'Pyro')
		self.createGroup(Pyro.config.PYRO_NS_DEFAULTGROUP)
		Log.msg("NameServer","Running in",
		 {Pyro.constants.NSROLE_SINGLE:"single",
		  Pyro.constants.NSROLE_PRIMARY:"primary",
		  Pyro.constants.NSROLE_SECONDARY:"secondary"}[self.role],"mode" )
			
	def _initialResyncWithTwin(self, twinProxy):
		if twinProxy:
			Log.msg("NameServer","Initial resync with other NS at",twinProxy.URI.address,"port",twinProxy.URI.port)
			print "Resyncing with other NS at",twinProxy.URI.address,"port",twinProxy.URI.port
			# keep old NS (self) registration
			oldNSreg=self.resolve(Pyro.constants.NAMESERVER_NAME)
			self.root=twinProxy._resync(NameServerProxy(self.getProxy().URI,noconnect=1))
			# reset self registration
			try:
				self.unregister(Pyro.constants.NAMESERVER_NAME)
			except:
				pass
			self.register(Pyro.constants.NAMESERVER_NAME,oldNSreg)
			self.otherNS=twinProxy
			
	def _removeTwinNS(self):
		self.otherNS=None
			
	def register(self,name,URI):
		(origname,name)=name,self.validateName(name)
		URI=self.validateURI(URI)
		self.lock.acquire()
		try:
			(group, name)=self.locateGrpAndName(name)
			if isinstance(group,NameValue):
				raise errors.NamingError('parent is no group')
			try:
				group.newleaf(name,URI)
				Log.msg('NameServer','registered',name,'with URI',str(URI))
				self.__dosynccall("register",origname,URI)
			except KeyError:
				Log.msg('NameServer','name already exists:',name)
				raise errors.NamingError('name already exists')
		finally:
			self.lock.release()

	def unregister(self,name):
		(origname,name)=name,self.validateName(name)
		self.lock.acquire()
		try:
			(group, name)=self.locateGrpAndName(name)
			try:
				group.cutleaf(name)
				Log.msg('NameServer','unregistered',name)
				self.__dosynccall("unregister",origname)
			except KeyError:
				raise errors.NamingError('name not found')
			except ValueError:
				Log.msg('NameServer','attempt to remove a group:',name)
				raise errors.NamingError('is a group')
		finally:
			self.lock.release()

	def resolve(self,name):
		# not thread-locked: higher performance and not necessary.
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			if isinstance(branch,NameValue):
				return branch.value
			else:
				Log.msg('NameServer','attempt to resolve groupname:',name)
				raise errors.NamingError('attempt to resolve groupname')
		except KeyError:
			raise errors.NamingError('name not found')
		except AttributeError:
			raise errors.NamingError('group not found')

	def flatlist(self):
		# return a dump
		self.lock.acquire()
		try:
			r=self.root.flatten()
		finally:
			self.lock.release()
		for i in range(len(r)):
			r[i]=(':'+r[i][0], r[i][1])
		return r

	def ping(self):
		# Just accept a remote invocation.
		# This method is used to check if NS is still running,
		# and also by the locator if a direct lookup is needed.
		pass

	# --- sync support (twin NS)
	def _resync(self, twinProxy):
		if self.role!=Pyro.constants.NSROLE_SINGLE:
			Log.msg("NameServer","resync requested from NS at",twinProxy.URI.address,"port",twinProxy.URI.port)
			print "Resync requested from NS at",twinProxy.URI.address,"port",twinProxy.URI.port
			self.otherNS=twinProxy
			self.lock.acquire()
			try:
				return self.root
			finally:
				self.lock.release()
		else:
			Log.warn("NameServer","resync requested from",twinProxy.URI,"but not running in correct mode")
			raise errors.NamingError("The (other) NS is not running in 'primary' or 'secondary' mode")
	
	# remotely called:
	def _synccall(self, method, *args):
		# temporarily disable the other NS
		oldOtherNS, self.otherNS = self.otherNS, None
		getattr(self, method) (*args)
		self.otherNS = oldOtherNS
		
	def resync(self):
		if self.role==Pyro.constants.NSROLE_SINGLE:
			raise errors.NamingError("NS is not running in 'primary' or 'secondary' mode")
		if self.otherNS:
			try:
				self._initialResyncWithTwin(self.otherNS)
				return
			except:
				pass
		raise errors.NamingError("cannot resync: twin NS is unknown or unreachable")

	# local helper:
	def __dosynccall(self, method, *args):
		if self.role!=Pyro.constants.NSROLE_SINGLE and self.otherNS:
			try:
				self.otherNS._synccall(method, *args)
			except Exception,x:
				Log.warn("NameServer","ignored error in _synccall - but removing other NS",x)
				self.otherNS=None
		
	# --- hierarchical naming support
	def createGroup(self,groupname):
		groupname=self.validateName(groupname)
		self.lock.acquire()
		try:
			(parent,name)=self.locateGrpAndName(groupname)
			try:
				parent.newbranch(name)
				Log.msg('NameServer','created group',groupname)
				self.__dosynccall("createGroup",groupname)
			except KeyError,x:
				raise errors.NamingError(x)
		finally:
			self.lock.release()

	def deleteGroup(self,groupname):
		groupname=self.validateName(groupname)
		if groupname==':':
			Log.msg('NameServer','attempt to deleteGroup root group')
			raise errors.NamingError('not allowed to delete root group')
		self.lock.acquire()
		try:
			(parent,name)=self.locateGrpAndName(groupname)
			try:
				parent.cutbranch(name)
				Log.msg('NameServer','deleted group',name)
				self.__dosynccall("deleteGroup",groupname)
			except KeyError:
				raise errors.NamingError('group not found')
			except ValueError:
				Log.msg('NameServer','attempt to deleteGroup a non-group:',groupname)
				raise errors.NamingError('is no group')
		finally:
			self.lock.release()
			
	def list(self,groupname):
		# not thread-locked: higher performance and not necessary.
		if not groupname:
			groupname=':'
		groupname=self.validateName(groupname)
		try:
			return self.getBranch(groupname).list()
		except KeyError:
			raise errors.NamingError('group not found')
		except AttributeError:
			Log.msg('NameServer','attempt to list a non-group:',groupname)
			raise errors.NamingError('is no group')
			
	# --- meta info support
	def setMeta(self, name, meta):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			branch.setMeta(meta)
			self.__dosynccall("setMeta",name,meta)
		except KeyError:
			raise errors.NamingError('name not found')
		except AttributeError:
			raise errors.NamingError('group not found')
	
	def getMeta(self, name):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			return branch.getMeta()
		except KeyError:
			raise errors.NamingError('name not found')
		except AttributeError:
			raise errors.NamingError('group not found')

	def _setSystemMeta(self, name, meta):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			branch.setSystemMeta(meta)
			self.__dosynccall("_setSystemMeta",name,meta)
		except KeyError:
			raise errors.NamingError('name not found')
		except AttributeError:
			raise errors.NamingError('group not found')
	
	def _getSystemMeta(self, name):
		name=self.validateName(name)
		try:
			branch=self.getBranch(name)
			return branch.getSystemMeta()
		except KeyError:
			raise errors.NamingError('name not found')
		except AttributeError:
			raise errors.NamingError('group not found')

	# --- private methods follow
	def locateGrpAndName(self,name):
		# ASSUME name is absolute (from root) (which is required here)
		idx=string.rfind(name,'.')
		if idx>=0:
			# name is hierarchical
			grpname=name[:idx]
			name=name[idx+1:]
			try:
				return (self.getBranch(grpname), name)
			except KeyError:
				raise errors.NamingError('(parent)group not found')
		else:
			# name is in root
			return (self.root, name[1:])

	def getBranch(self,name):
		# ASSUME name is absolute (from root) (which is required here)
		name=name[1:]
		if name:
			return reduce(lambda x,y: x[y], string.split(name,'.'), self.root)
		else:
			return self.root

	def validateName(self,name):
		if len(name)>=1 and name[0]==':':
			if ('' not in string.split(name,'.')):
				for i in name:
					if ord(i)<33 or ord(i)>126:
						raise errors.NamingError('invalid name')
				return name
			else:
				raise errors.NamingError('invalid name')
		else:
			# name is not absolute. Make it absolute.
			return _expandName(name)

	def validateURI(self,URI):
		if isinstance(URI, core.PyroURI):
			return URI
		try:
			u = core.PyroURI('')
			u.reinitFromString(URI)
			return u
		except:
			raise errors.NamingError('invalid URI')

	def publishURI(self, uri, verbose=0):
		# verbose is not used - always prints the uri.
		uri=str(uri)
		print 'URI is:',uri
		try:
			f=open(Pyro.config.PYRO_NS_URIFILE,'w')
			f.write(uri+'\n'); f.close()
			print 'URI written to:',Pyro.config.PYRO_NS_URIFILE
			Log.msg('NameServer','URI written to',Pyro.config.PYRO_NS_URIFILE)
		except:
			Log.warn('NameServer','Couldn\'t write URI to',Pyro.config.PYRO_NS_URIFILE)

#############################################################################
#
#	NamedTree data type. Used for the hierarchical name server.
#
#############################################################################

class NameSpaceSystemMeta:
	def __init__(self, timestamp, owner):
		self.timestamp=timestamp
		self.owner=owner
	def __str__(self):
		return "[timestamp="+str(self.timestamp)+" owner="+str(self.owner)+"]"

		
# All nodes in the namespace (groups, or namevalue pairs--leafs) have
# a shared set of properties, most notably: meta information.
class NameSpaceNode:
	def __init__(self, name, meta, owner):
		self.name=name
		self.systemMeta = NameSpaceSystemMeta(time.time(), owner)
		self.userMeta = meta
	def getMeta(self):
		# print "GETTING META OF",self,type(self)		# XXX
		return self.userMeta
	def getSystemMeta(self):
		# print "GETTING SYSMETA OF",self,type(self)		# XXX
		return self.systemMeta
	def setMeta(self,meta):
		self.userMeta=meta
	def setSystemMeta(self,meta):
		if isinstance(meta, NameSpaceSystemMeta):
			self.systemMeta=meta
		else:
			raise TypeError("system meta info must be NameSpaceSystemMeta object")

class NameValue(NameSpaceNode):
	def __init__(self, name, value=None, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.value=value

class NamedTree(NameSpaceNode):
	def __init__(self, name, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.branches={}
	def newbranch(self,name):
		if name in self.branches.keys():
			raise KeyError,'duplicate name'
		t = NamedTree(name)
		self.branches[name]=t
		return t
	def newleaf(self,name,value=None):
		if name in self.branches.keys():
			raise KeyError,'duplicate name'
		l = NameValue(name,value)
		self.branches[name]=l
		return l
	def cutleaf(self,name):
		if isinstance(self.branches[name], NameValue):
			del self.branches[name]
		else:
			raise ValueError,'not a leaf'
	def cutbranch(self,name):
		if isinstance(self.branches[name], NamedTree):
			del self.branches[name]
		else:
			raise ValueError,'not a branch'
	def __getitem__(self,name):
		return self.branches[name]
	def list(self):
		l=[]
		for (k,v) in self.branches.items():
			if isinstance(v, NamedTree):
				l.append( (k,0) )	# tree
			elif isinstance(v, NameValue):
				l.append( (k,1) )	# leaf
			else:
				raise ValueError('corrupt tree')
		return l
	def flatten(self,prefix=''):
		flat=[]
		for (k,v) in self.branches.items():
			if isinstance(v, NameValue):
				flat.append( (prefix+k, v.value) )
			elif isinstance(v, NamedTree):
				flat.extend(v.flatten(prefix+k+'.'))
		return flat
				

		
#############################################################################
#
#	The Persistent Name Server (a Pyro Object).
#	This implementation uses the hierarchical file system to
#	store the groups (as directories) and objects (as files).
#
#############################################################################

class PersistentNameServer(NameServer):
	def __init__(self, dbdir=None, role=Pyro.constants.NSROLE_SINGLE):
		# root is not a NamedTree but a directory
		self.dbroot=os.path.join(Pyro.config.PYRO_STORAGE,dbdir or 'Pyro_NS_database')
		try:
			os.mkdir(self.dbroot)
		except OSError,x:
			if x.errno not in (errno.EEXIST, errno.EBUSY):
				raise
		try:
			NameServer.__init__(self, role=role)
		except errors.NamingError:
			pass
		# make sure that the 2 initial groups (Pyro and Default) exist
		try: self.createGroup(':'+'Pyro')
		except errors.NamingError: pass
		try: self.createGroup(Pyro.config.PYRO_NS_DEFAULTGROUP)
		except errors.NamingError: pass

	def getDBDir(self):
		return self.dbroot

	def register(self,name,URI):
		name=self.validateName(name)
		URI=self.validateURI(URI)
		file=self.translate(name)
		self.lock.acquire()
		try:
			if os.access(file,os.R_OK):
				Log.msg('NameServer','name already exists:',name)
				raise errors.NamingError('name already exists')
			try:
				open(file,'w').write(str(URI)+'\n')
				Log.msg('NameServer','registered',name,'with URI',str(URI))
			except IOError,x:
				if x.errno==errno.ENOENT:
					raise errors.NamingError('(parent)group not found')
				elif x.errno==errno.ENOTDIR:
					raise errors.NamingError('parent is no group')
				else:
					raise errors.NamingError(x)
		finally:
			self.lock.release()

	def unregister(self,name):
		name=self.validateName(name)
		file=self.translate(name)
		self.lock.acquire()
		try:
			try:
				os.remove(file)
				Log.msg('NameServer','unregistered',name)
			except OSError,x:
				if x.errno==errno.ENOENT:
					raise errors.NamingError('name not found')
				elif x.errno==errno.EISDIR:
					Log.msg('NameServer','attempt to remove a group:',name)
					raise errors.NamingError('is a group')
				else:
					raise errors.NamingError(x)
		finally:
			self.lock.release()
			
	def resolve(self,name):
		# not thread-locked: higher performance and not necessary.
		name=self.validateName(name)
		file = self.translate(name)
		try:
			u = core.PyroURI('')
			u.reinitFromString(open(file).read())
			return u
		except IOError,x:
			if x.errno==errno.ENOENT:
				raise errors.NamingError('name not found')
			elif x.errno==errno.EISDIR:
				Log.msg('NameServer','attempt to resolve groupname:',name)
				raise errors.NamingError('attempt to resolve groupname')
			else:
				raise errors.NamingError(x)

	def flatlist(self):
		dbroot=self.translate(':')
		self.lock.acquire()
		try:
			files=self._filelist(dbroot,dbroot)
			list=[]
			for f in files:
				list.append((f, self.resolve(f)))
			return list
		finally:
			self.lock.release()

	# --- hierarchical naming support
	def createGroup(self,groupname):
		groupname=self.validateName(groupname)
		file = self.translate(groupname)
		self.lock.acquire()
		try:
			try:
				os.mkdir(file)
				Log.msg('NameServer','created group',groupname)
			except OSError,x:
				if x.errno in (errno.EEXIST, errno.EBUSY):
					raise errors.NamingError('duplicate name')
				elif x.errno == errno.ENOENT:
					raise errors.NamingError('(parent)group not found')
				else:
					raise errors.NamingError(x)
		finally:
			self.lock.release()

	def deleteGroup(self,groupname):
		groupname=self.validateName(groupname)
		if groupname==':':
			Log.msg('NameServer','attempt to deleteGroup root group')
			raise errors.NamingError('not allowed to delete root group')
		file = self.translate(groupname)
		self.lock.acquire()
		try:
			if not os.access(file,os.R_OK):
				raise errors.NamingError('group not found')
			try:
				shutil.rmtree(file)
				Log.msg('NameServer','deleted group',groupname)
			except OSError,x:
				if x.errno==errno.ENOENT:
					raise errors.NamingError('group not found')
				elif x.errno==errno.ENOTDIR:
					Log.msg('NameServer','attempt to deleteGroup a non-group:',groupname)
					raise errors.NamingError('is no group')
				else:
					raise errors.NamingError(x)
		finally:
			self.lock.release()
			
	def list(self,groupname):
		if not groupname:
			groupname=':'
		groupname=self.validateName(groupname)
		dir=self.translate(groupname)
		self.lock.acquire()
		try:
			if os.access(dir,os.R_OK):
				if os.path.isfile(dir):
					Log.msg('NameServer','attempt to list a non-group:',groupname)
					raise errors.NamingError('is no group')
				else:
					l = dircache.listdir(dir)
					list = []
					for e in l:
						if os.path.isdir(os.path.join(dir,e)):
							list.append((e,0))		# dir has code 0
						else:
							list.append((e,1))		# leaf has code 1
					return list
			raise errors.NamingError('group not found')
		finally:
			self.lock.release()


	# --- private methods follow

	# recursive file listing, output is like "find <path> -type f"
	# but using NS group separator chars
	def _filelist(self,root,path):
		try:
			(filez,dirz) = util.listdir(path)
		except OSError:
			raise errors.NamingError('group not found')
			
		files=[]
		for f in filez:
			if path==root:
				files.append(':'+f)
			else:
				p=string.replace(path[len(root):], os.sep, '.')
				files.append(':'+p+'.'+f)
		for d in dirz:
			files.extend(self._filelist(root,os.path.join(path,d)))
		return files

	# Pyro NS name to filesystem path translation
	def translate(self,name):
		if name[0]==':':
			name=name[1:]
		args=[self.dbroot]+string.split(name,'.')
		return os.path.join(*args)

	def getBranch(self,name):
		tr = self.translate(name)
		if os.path.exists(tr):
			return PersistentNameSpaceNode(filename=tr+".ns_meta")
		else:
			raise errors.NamingError('name not found')

class PersistentNameSpaceNode(NameSpaceNode):
	def __init__(self, filename, name=None, meta=None, owner=None):
		NameSpaceNode.__init__(self, name, meta, owner)
		self.filename=filename
		if not name:
			# init from file
			try:
				(sysmeta, usermeta)=util.getPickle().load(open(self.filename,"rb"))
				NameSpaceNode.setSystemMeta(self, sysmeta)
				NameSpaceNode.setMeta(self, usermeta)
			except Exception,x:
				pass # XXX just accept empty meta...
		else:
			# write to file
			self._writeToFile()
	def setMeta(self,meta):
		NameSpaceNode.setMeta(self, meta)
		self._writeToFile()
	def setSystemMeta(self,meta):
		NameSpaceNode.setSystemMeta(self, meta)
		self._writeToFile()
	def _writeToFile(self):
		util.getPickle().dump( (self.getSystemMeta(), self.getMeta()) , open(self.filename,"wb"), Pyro.config.PYRO_PICKLE_FORMAT)
		

		
#############################################################################
#
# The broadcast server which listens to broadcast requests of clients who
# want to discover our location, or send other system commands.
#
#############################################################################


class BroadcastServer(SocketServer.UDPServer):

	nameServerURI = ''	# the Pyro URI of the Name Server

	def __init__(self, addr, bcRequestHandler,norange=0):
		if norange:
			portrange=1
		else:
			portrange=Pyro.config.PYRO_PORT_RANGE
		(location,port)=addr
		for port in range(port, port+portrange):
			try:
				SocketServer.UDPServer.__init__(self, (location,port), bcRequestHandler)
				return			# got it!
			except socket.error,x:
				continue		# try the next port in the list
		raise    # port range exhausted... re-raise the socket error.
		
	def server_activate(self):
		self.requestValidator=lambda x,y: 1  # default: accept all
		self.shutdown=0				# should the server loop stop?
		self.preferredTimeOut=3.0	# preferred timeout for the server loop
			
	def setNS_URI(self,URI):
		self.nameServerURI=str(URI)
	def setRequestValidator(self, validator):
		self.requestValidator=validator
	def keepRunning(self, keep):
		self.ignoreShutdown = keep	# ignore shutdown requests (i.e. keep running?)

	def bcCallback(self,ins):
		for i in ins:
			i.handle_request()

	def verify_request(self, req, addr):
		return self.requestValidator(req, addr)

	def getServerSocket(self):
		return self.socket
	
		
class bcRequestHandler(SocketServer.BaseRequestHandler):
	def handle(self):
		Log.msg('BroadcastServer','incoming request from',str(self.client_address[0]))
		# request is a simple string
		cmd = self.request[0]
		if cmd=='location':
			# somebody wants to know our location, give them our URI
			self.request[1].sendto(self.server.nameServerURI,self.client_address)
		elif cmd=='shutdown':
			# we should die!?
			if self.server.ignoreShutdown:
				Log.msg('BroadcastServer','Shutdown ignored.')
				self.request[1].sendto('Shutdown request denied',self.client_address)
			else:
				Log.msg('BroadcastServer','Shutdown received.')
				print 'BroadcastServer received shutdown request... will shutdown shortly...'
				self.request[1].sendto('Will shut down shortly',self.client_address)
				self.server.shutdown=1
		else:
			Log.warn('BroadcastServer','Invalid command ignored:',cmd)

# The default BC request validator... accepts everything
# You must subclass this for your own validators
class BCReqValidator:
	def __call__(self, req, addr):
		(cmd,self.sock)=req
		self.addr=addr
		if cmd=='location':
			return self.acceptLocationCmd()
		elif cmd=='shutdown':
			return self.acceptShutdownCmd()
		else:
			return 0
	def reply(self,msg):
		self.sock.sendto(msg,self.addr)
	def acceptLocationCmd(self):
		return 1
	def acceptShutdownCmd(self):
		return 1


#############################################################################

class NameServerStarter:
	def __init__(self, identification=None):
		core.initServer()
		self.identification=identification
		self.started = Pyro.util.getEventObject()
	def start(self, *args, **kwargs):			# see _start for allowed arguments
		self._start( startloop=1, *args, **kwargs )
	def initialize(self, *args, **kwargs):		# see _start for allowed arguments
		self._start( startloop=0, *args, **kwargs )
	def getServerSockets(self):
		return self.daemon.getServerSockets() + [self.bcserver.getServerSocket()]
	def waitUntilStarted(self,timeout=None):
		self.started.wait(timeout)
		return self.started.isSet()
	def _start(self,hostname='', nsport=0, bcport=0, keep=0, persistent=0, dbdir=None, Guards=(None,None), allowmultiple=0, verbose=0, startloop=1, role=(constants.NSROLE_SINGLE,None) ):
		if not nsport:
			if role[0]==constants.NSROLE_SECONDARY:
				nsport=Pyro.config.PYRO_NS2_PORT
			else:
				nsport=Pyro.config.PYRO_NS_PORT
		if not bcport:
			if role[0]==constants.NSROLE_SECONDARY:
				bcport=Pyro.config.PYRO_NS2_BC_PORT
			else:
				bcport=Pyro.config.PYRO_NS_BC_PORT
		otherNSuri=None

		try:
			retries=Pyro.config.PYRO_BC_RETRIES
			timeout=Pyro.config.PYRO_BC_TIMEOUT
			Pyro.config.PYRO_BC_RETRIES=1
			Pyro.config.PYRO_BC_TIMEOUT=1
			try:
				otherNSuri=NameServerLocator().detectNS()
			except errors.PyroError:
				pass
			else:
				print 'The Name Server appears to be already running on this segment.'
				print '(host:',otherNSuri.address,' port:',otherNSuri.port,')'
				if allowmultiple:
					print 'WARNING: starting another Name Server in the same segment!'
				elif role[0] in (constants.NSROLE_PRIMARY, constants.NSROLE_SECONDARY):
					pass
				else:
					msg='Cannot start multiple Name Servers in the same network segment.'
					print msg
					raise errors.NamingError(msg)

			if role[0]!=Pyro.constants.NSROLE_SINGLE:
				print "Locating twin NameServer."
				# Do this before starting our own daemon, otherwise possible deadlock!
				# This step is done here to make pretty certain that one of both name
				# servers finds the other either *now*, or else later on (below).
				# If we omit this step here, deadlock may occur on the attempt below!
				otherNS = self.locateTwinNS(role, otherNSuri)
				if otherNS:
					print "Found twin NameServer at",otherNS.URI.address,"port",otherNS.URI.port
					role=(role[0], otherNS)
	
			Pyro.config.PYRO_BC_RETRIES=retries
			Pyro.config.PYRO_BC_TIMEOUT=timeout
			daemon = core.Daemon(host=hostname, port=nsport,norange=1)
		except errors.DaemonError,x:
			print 'The Name Server appears to be already running on this host.'
			print '(or somebody else occupies our port,',nsport,')'
			print 'It could also be that the address \''+hostname+'\' is not correct.'
			print 'Name Server was not started!'
			raise

		if self.identification:
			daemon.setAllowedIdentifications([self.identification])
			print 'Requiring connection authentication.'
		if Guards[0]:
			daemon.setNewConnectionValidator(Guards[0])

		if persistent:
			ns=PersistentNameServer(dbdir,role=role[0])
			daemon.useNameServer(ns)
			NS_URI=daemon.connectPersistent(ns,constants.NAMESERVER_NAME)
		else:
			ns=NameServer(role=role[0])
			daemon.useNameServer(ns)
			NS_URI=daemon.connect(ns,constants.NAMESERVER_NAME)

		# Try to start the broadcast server. Binding on the magic "<broadcast>"
		# address should work, but on some systems (windows) it doesn't.
		# Therefore we first try "<broadcast>", if that fails, try "".
		self.bcserver=None
		notStartedError=""
		for bc_bind in ("<broadcast>", ""):
			try:
				self.bcserver = BroadcastServer((bc_bind,bcport),bcRequestHandler,norange=1)
			except socket.error,x:
				notStartedError += str(x)+" "
		if not self.bcserver:
			print 'Cannot start broadcast server. Is somebody else occupying our broadcast port?'
			print 'The error(s) were:',notStartedError
			print '\nName Server was not started!'
			raise errors.NamingError("cannot start broadcast server")
	
		if Guards[1]:
			self.bcserver.setRequestValidator(Guards[1])
		self.bcserver.keepRunning(keep)
		if verbose:
			if keep:
				print 'Will ignore shutdown requests.'
			else:
				print 'Will accept shutdown requests.'

			print 'Name server listening on:',daemon.sock.getsockname()
			print 'Broadcast server listening on:',self.bcserver.socket.getsockname()

		if Guards[0] or Guards[1]:
			if verbose:
				print 'Using security plugins:'
			if Guards[0]:
				clazz=Guards[0].__class__
				if verbose:
					print '  NS new conn validator =',clazz.__name__,'from', clazz.__module__, ' ['+sys.modules.get(clazz.__module__).__file__+']'
			elif verbose: print '  default NS new conn validator'
			if Guards[1]:
				clazz=Guards[1].__class__
				if verbose:
					print '  BC request validator  =',clazz.__name__,'from', clazz.__module__, ' ['+sys.modules.get(clazz.__module__).__file__+']'
			elif verbose: print '  default BC request validator'

		ns.publishURI(NS_URI,verbose)

		self.bcserver.setNS_URI(NS_URI)
		Log.msg('NS daemon','This is the Pyro Name Server.')
		if persistent:
			Log.msg('NS daemon','Persistent mode, database is in',ns.getDBDir())
			if verbose:
				print 'Persistent mode, database is in',ns.getDBDir()
		Log.msg('NS daemon','Starting on',daemon.hostname,'port', daemon.port, ' broadcast server on port',bcport)

		if role[0]==constants.NSROLE_PRIMARY:
			print "Primary",
		elif role[0]==constants.NSROLE_SECONDARY:
			print "Secondary",
		print 'Name Server started.'

		# If we run in primary or secondary mode, resynchronize
		# the NS database with the other name server.
		# Try again to look it up if it wasn't found before.
		
		if role[0]!=Pyro.constants.NSROLE_SINGLE:
			if not otherNS:
				# try again to contact the other name server
				print "Locating twin NameServer again."
				otherNS = self.locateTwinNS(role, otherNSuri)
				role=(role[0], otherNS)
			if otherNS:
				# finally got it, resync!
				print "Found twin NameServer at",otherNS.URI.address,"port",otherNS.URI.port
				ns._initialResyncWithTwin(otherNS)

		self.started.set()   # signal that we've started (for external threads)
		
		if startloop:
			# I use a timeout here otherwise you can't break gracefully on Windoze
			try:
				daemon.setTimeout(20)  # XXX fixed timeout
				daemon.requestLoop(lambda s=self: not s.bcserver.shutdown,
					self.bcserver.preferredTimeOut,[self.bcserver],self.bcserver.bcCallback)
				if self.bcserver.shutdown:
					self.shutdown(ns)
			except KeyboardInterrupt:
				Log.warn('NS daemon','shutdown on user break signal')
				print 'Shutting down on user break signal.'
				self.shutdown(ns)
			except:
				try:
					import traceback
					(exc_type, exc_value, exc_trb) = sys.exc_info()
					out = ''.join(traceback.format_exception(exc_type, exc_value, exc_trb)[-5:])
					Log.error('NS daemon', 'Unexpected exception, type',exc_type,
						'\n--- partial traceback of this exception follows:\n',
						out,'\n--- end of traceback')
					print '*** Exception occured!!! Partial traceback:'
					print out
					print '*** Resuming operations...'
				finally:	
					del exc_type, exc_value, exc_trb

			Log.msg('NS daemon','Shut down gracefully.')
			print 'Name Server gracefully stopped.'
		else:
			# Do not enter the loop. Keep the objects needed for getServerSockets:
			# self.bcserver=self.bcserver
			self.daemon=daemon
			self.daemon.setTimeout(20)  # XXX fixed timeout


	def locateTwinNS(self, role, otherNSuri):
		try:
			retries=Pyro.config.PYRO_BC_RETRIES
			timeout=Pyro.config.PYRO_BC_TIMEOUT
			Pyro.config.PYRO_BC_RETRIES=1
			Pyro.config.PYRO_BC_TIMEOUT=1
			try:
				if role[1]:
					(host,port)=(role[1]+':').split(':')[:2]
					if len(port)==0:
						port=None
					else:
						port=int(port)
					otherNS=NameServerLocator().getNS(host,port,trace=0)
				else:
					if otherNSuri:
						otherNS=NameServerLocator().getNS(host=otherNSuri.address, port=otherNSuri.port, trace=0)
					else:
						if role[0]==Pyro.constants.NSROLE_PRIMARY:
							port=Pyro.config.PYRO_NS2_BC_PORT
						else:
							port=Pyro.config.PYRO_NS_BC_PORT
						otherNS=NameServerLocator().getNS(host=None,port=port,trace=0)
				Log.msg("NameServerStarted","Found twin NS at",otherNS.URI)
				return otherNS
			except Exception,x:
				print "WARNING: Cannot find twin NS yet: ",x
				Log.msg("NameServerStarter","Cannot find twin NS yet:",x)
				return None
		finally:
			Pyro.config.PYRO_BC_RETRIES=retries
			Pyro.config.PYRO_BC_TIMEOUT=timeout
			

	def handleRequests(self,timeout=None):
		# this method must be called from a custom event loop
		self.daemon.handleRequests(timeout, [self.bcserver], self.bcserver.bcCallback)
		if self.bcserver.shutdown:
			self.shutdown()

	def shutdown(self, ns=None):
		if ns:
			# internal shutdown call with specified NS object
			daemon=ns.getDaemon()
		else:
			# custom shutdown call w/o specified NS object, use stored instance
			daemon=self.daemon
			ns=daemon.getNameServer()
			del self.daemon
		ns._removeTwinNS()
		daemon.disconnect(ns) # clean up nicely
		self.bcserver.shutdown=1
		daemon.shutdown()

def main(argv):
	Args = util.ArgParser()
	Args.parse(argv,'hkmvn:p:b:d:s:i:1:2:')
	if Args.hasOpt('h'):
		print 'Usage: ns [-h] [-k] [-m] [-n hostname] [-p port] [-b port]'
		print '          [-i identification] [-d [databasefile]] [-s securitymodule]'
		print '          [-1 [host:port]] [-2 [host:port]] [-v]'
		print '  where -p = NS server port'
		print '        -b = NS broadcast port'
		print '        -n = non-default hostname to bind on'
		print '        -m = allow multiple instances in network segment'
		print '        -k = keep running- do not respond to shutdown requests'
		print '        -d = use persistent database, provide optional storage directory'
		print '        -s = use given python module with security plugins'
		print '        -i = specify the required authentication ID'
		print '        -1 = runs this NS as primary, opt. specify where secondary is'
		print '        -2 = runs this NS as secondary, opt. specify where primary is'
		print '        -v = verbose output'
		print '        -h = print this help'
		raise SystemExit
	host = Args.getOpt('n','')
	port = int(Args.getOpt('p',0))
	bcport = int(Args.getOpt('b',0))
	
	role=constants.NSROLE_SINGLE
	roleArgs=None
	if Args.hasOpt('1'):
		role=constants.NSROLE_PRIMARY
		roleArgs=Args.getOpt('1')
	if Args.hasOpt('2'):
		role=constants.NSROLE_SECONDARY
		roleArgs=Args.getOpt('2')

	ident = Args.getOpt('i',None)
	verbose = Args.hasOpt('v')
	keep=Args.hasOpt('k')
	allowmultiple=Args.hasOpt('m')

	try:
		dbdir = Args.getOpt('d')
		persistent = 1
	except KeyError:
		persistent = 0
		dbdir = None

	try:
		secmod = __import__(Args.getOpt('s'),locals(),globals())
		Guards = (secmod.NSGuard(), secmod.BCGuard())
	except ImportError,x:
		print 'Error loading security module:',x
		print '(is it in your python import path?)'
		raise SystemExit
	except KeyError:
		secmod = None
		Guards = (None,None)

	Args.printIgnored()
	if Args.args:
		print 'Ignored arguments:',string.join(Args.args)

	print '*** Pyro Name Server ***'
	if ident:
		starter=NameServerStarter(identification=ident)
	else:
		starter=NameServerStarter()

	try:
		starter.start(host,port,bcport,keep,persistent,dbdir,Guards,allowmultiple,verbose,role=(role,roleArgs))
	except (errors.NamingError, errors.DaemonError),x:
		# this error has already been printed, just exit.
		pass
