#############################################################################
#
#	$Id: pyroc.py,v 2.14 2003/03/21 00:35:32 irmen Exp $
#	Python Remote Objects Proxy Compiler.
#
#	This is part of "Pyro" - Python Remote Objects
#	which is (c) Irmen de Jong - irmen@users.sourceforge.net
#
#	Known shortcoming: can't deal fully with Python packages.
#
##############################################################################

import sys, types
import os, time
import Pyro
import constants
from core import *


fileHeader = """############################################################################
#
# This code has been generated by PyroC - the Python Remote Object Compiler
#
# Do not make changes in this file!
#
############################################################################
"""

#############################################################################
#
#	ClassInfo	- class info objects
#
#############################################################################

class ClassInfo:
	def __init__(self, clazz):
		self.clazz = clazz
		self.modulename = clazz.__module__
		self.classname = clazz.__name__
		self.bases = clazz.__bases__
	def filterAndGetMethods(self, clazz):
		# This function gets all members of clazz, filters the methods,
		# and returns a list of method description objects.
		methods=[]
		for member in dir(clazz):
			memberInstance = getattr(clazz,member)
			if type(memberInstance)==types.MethodType:
				m = Method(memberInstance)
				methods.append(m)
		return methods

	def getAllMethods_recurse(self,clazz):
		# Recursive method scanner.
		# Stop condition: the class has no more base classes.
		# (in this case, the for loop and recursion is not entered)
		if clazz is ObjBase:
			print '** Note: ignored Pyro.core.ObjBase methods'
			return []
		methods=self.filterAndGetMethods(clazz)	# our own methods
		for c in clazz.__bases__:
			basemethods = self.getAllMethods_recurse(c)
			for bm in basemethods:
				if bm not in methods:
					methods.append(bm)
		return methods
	def getAllMethods(self):
		# This method will walk up the inheritance tree and create a list
		# of all methods, inherited or overridden.
		return self.getAllMethods_recurse(self.clazz)
		


#############################################################################
#
#	CodeGenerator	- the workhorse
#
#############################################################################

class CodeGenerator:
	classes=[]

	# genProxy - generates Client Proxy code		
	def genProxy(self,output):
		output.write(fileHeader)
		output.write('\n# Generated '+time.ctime(time.time())+' by PyroC V'+constants.VERSION+'\n\n')
		output.write('# THIS IS THE CLIENT SIDE PROXY CODE\n\n')
		output.write('import Pyro.protocol\n\n')
		for ci in self.classes:
			print 'Generating proxy for',ci.classname,
			output.write('class '+ci.classname+': ')
			if ci.bases:
				print '- a subclass from',
				output.write(' # originally subclassed from ')
				for sup in ci.bases:
					if sup.__module__!=ci.modulename:
						output.write(sup.__module__+'.')
					output.write(sup.__name__ + ',')
					print sup.__name__,
					if sup is ObjBase:
						print '(IGNORED)',
				if len(ci.bases)>=1:
					output.seek(-1,1)	# remove last comma
			print
			output.write("""
	def __init__(self,URI):
		self.__dict__['URI'] = URI
		self.__dict__['objectID'] = URI.objectID
		self.__dict__['adapter'] = Pyro.protocol.getProtocolAdapter(URI.protocol)
		self.adapter.bindToURI(URI)
	def _setOneway(self, methods):
		if type(methods) not in (type([]), type((0,))):
			methods=(methods,)
		self.adapter.setOneway(methods)
	def _setTimeout(self, timeout):
		self.adapter.setTimeout(timeout)
	def _setIdentification(self, ident):
		self.adapter.setIdentification(ident)
	def _setNewConnectionValidator(self, validator):
		self.adapter.setNewConnectionValidator(validator)
	def _release(self):
		if self.adapter:
			self.adapter.release()
	def __getattr__(self, attr):
		return self.adapter.remoteInvocation('_r_ga',0,attr)
	def __setattr__(self, attr, value):
		return self.adapter.remoteInvocation('_r_sa',0,attr,value)
	def __hash__(self):
		return hash(self.objectID)
	def __lt__(self,other):
		return self.objectID<other.objectID
	def __gt__(self,other):
		return self.objectID>other.objectID
	def __eq__(self,other):
		return self.objectID==other.objectID
	def __cmp__(self,other):
		return cmp(self.objectID,other.objectID)
	def __nonzero__(self):
		return 1
""")
			output.write("\tdef __copy__(self):\n\t\treturn "+ci.classname+"(self.URI)\n")
			# generate proxy method for each 'real method'
			for method in ci.getAllMethods():
				if method.isSpecial():
					print '** Warning, skipped special method',method.name
					continue
				output.write('\tdef '+str(method)+':\n')
				flags=0
				if method.usesVarargs:
					flags=flags|constants.RIF_Varargs
				if method.usesKeywords:
					flags=flags|constants.RIF_Keywords
				output.write('\t\treturn self.adapter.remoteInvocation(\''+method.name+'\','+ str(flags))
				if method.hasArgs():
					output.write(','+method.argsToString(0))
				output.write(')\n')
			output.write('\n')

	# genSkeleton - generates Server Skeleton code (for now, does nothing)
	def genSkeleton(self,output):
		print 'This release of Pyro doesn\'t need server-side skeleton code.'

	# processModule - reads and processes the module for which proxies should be generated
	def processModule(self, module):
		print 'processing module \''+module.__name__+'\' ('+module.__file__+')...'
	
		# Iterate through all members of the module.
		# If it's a class, process it, otherwise we're not interested.
		for member in dir(module):
			memberInstance = getattr(module,member)
			if type(memberInstance)==types.ClassType:
				self.processClass(memberInstance,module)
			
	# processClass - processes a class for which a proxy should be generated
	def processClass(self, clazz, module):
		print 'examining class',clazz.__name__,'... '
		# We must skip classes which were imported from other modules
		if clazz.__module__!=module.__name__:
			print 'imported from another module. Skipped.'
			return
		# XXX We can't process packages
		if '.' in clazz.__module__:
			noPackages('class '+clazz.__name__+' from module '+clazz.__module__)
		self.classes.append(ClassInfo(clazz))	# add the new class

#############################################################################
#
#	Method	- abstraction for a class method.
#
#############################################################################

class Method:
	name=''
	args=()
	usesVarargs=0			# uses '*arguments' syntax
	usesKeywords=0			# uses '**keywords' syntax
	normalArgCount=0		# number of 'normal' arguments (not * or **)
	
	def __init__(self,methodInstance):
		self.name=methodInstance.__name__
		# get the code object and from there, the argument names
		if type(methodInstance.im_func)==types.BuiltinFunctionType:
			return
			print '*** Assuming varargs for builtin function:',self.name
			self.usesVarargs=1
			self.args=('self','args')
			return
		code = methodInstance.im_func.func_code
		argCount = code.co_argcount
		self.normalArgCount = argCount
		if code.co_flags & (1<<2):
			# method uses '*arg' parameter
			self.usesVarargs=1
			argCount = argCount+1
		if code.co_flags & (1<<3):
			# method uses '**arg' parameter
			self.usesKeywords=1
			argCount = argCount+1
		argNames = ('self',) + code.co_varnames[1:argCount] # rename the 'self' arg
		self.args=argNames
	def __str__(self):
		return self.name+'('+self.argsToString(1)+')'
	def __cmp__(self, other):
		return self.name!=other.name
	def isSpecial(self):
		return len(self.name)>=4 and  \
			self.name[0:2]=='__' and self.name[-2:]=='__'
	def hasArgs(self):
		if self.usesVarargs or self.usesKeywords:
			return 1
		return self.normalArgCount-1	# don't count self

	# argsToString - convert the method's arguments to a string.
	#  if methodDef is true, the string is used for a method DEFINITION,
	#   (where we still need the 'self' arg and the '*' and '**',
	#  otherwise it is used for a method CALL, where the
	#   'self' and '*' and '**' are omitted.

	def argsToString(self,methodDef):
		if methodDef:
			asterisk='*'
			argCnt = self.normalArgCount
			args = self.args
		else:
			asterisk=''
			argCnt = self.normalArgCount-1		# remove the 'self' argument
			args = self.args[1:]				#    ...
		s=''
		if argCnt>0:
			for arg in args[:argCnt-1]:
				s=s+arg+','
			s=s+args[argCnt-1]
			if self.usesVarargs:
				s=s+','+asterisk+args[argCnt]
				argCnt=argCnt+1		# so that the if statement below uses the next arg
			if self.usesKeywords:
				s=s+','+asterisk+asterisk+args[argCnt]
		else:
			# no args, don't add a comma
			if self.usesVarargs:
				s=s+asterisk+args[argCnt]
				argCnt=argCnt+1		# so that the if statement below uses the next arg
			if self.usesKeywords:
				if self.usesVarargs:
					# add a comma between the Vargs and the Kargs
					s=s+','
				s=s+asterisk+asterisk+args[argCnt]
		return s



############ Fire up the barbecue ##########

def noPackages(where):
	print '\n\n*** ERROR! Currently, Python packages are not supported by Pyroc! ***'
	print '*** Can\'t process: ',where
	raise SystemExit

def main(argv):
	args = argv
	if len(args) != 1:
		print 'You must provide one argument: the name of a module to process.'
		raise SystemExit
	
	print 'Python Remote Object Compiler (c) Irmen de Jong. Pyro V'+constants.VERSION+'\n'

	cwd = os.getcwd()
	if not cwd in sys.path:
		sys.path.insert(0,cwd)
		print '[added current directory to import path]'

	if '.' in args[0]:
		noPackages(args[0])

	try:
		module = __import__(args[0], {}, {})
	except Exception,x:
		print 'Big error while importing the module to process!!!'
		print x
		raise SystemExit(1)

	proxyGen = CodeGenerator()
	proxyGen.processModule(module)
	
	outfile_proxy = module.__name__+'_proxy.py'
	outfile_skel  = module.__name__+'_skel.py'
	
	of = open(outfile_proxy,'w')
	proxyGen.genProxy(of)
	print 'This release of Pyro doesn\'t need server-side skeleton code.'
	# of = open(outfile_skel,'w')
	# proxyGen.genSkeleton(of)
	print '\nAll done. Output can be found in',outfile_proxy,'.\n'

