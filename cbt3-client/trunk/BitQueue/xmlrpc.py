#!/usr/bin/python

import SocketServer
from threading import Thread
from SimpleXMLRPCServer import SimpleXMLRPCServer,SimpleXMLRPCRequestHandler
import xmlrpclib
import select
import socket
import urllib
import os
from types import *

from queue import QueueEntry
from BitQueue import version,BindException
import policy
from i18n import *

def xml_escape(o,escape=urllib.quote):
    to = type(o)
    if to in StringTypes:
        o = escape(o)
    elif to == TupleType:
        o = tuple([xml_escape(i,escape) for i in list(o)])
    elif to == ListType:
        o = [xml_escape(i,escape) for i in o]
    elif to == DictType:
        n = {}
        for key in o.keys():
            n[key] = xml_escape(o[key],escape)
        o = n
    return o

def xml_unescape(o,unescape=urllib.unquote):
    return xml_escape(o,unescape)

class CommandResponse:
    def __init__(self,result='',error=None):
        self.result = result
        if not result and not error and not error is None:
            import traceback
            self.error = ''.join(traceback.format_stack()[:-1])
        self.error = error or ''

    def getreply(self):
        return self.result

    def geterror(self):
        return self.error

    def encode(self):
        return {'reply':xml_escape(self.result),
                'error':xml_escape(self.error)}

    def decode(self,dict):
        self.result = xml_unescape(dict.get('reply',''))
        self.error = xml_unescape(dict.get('error',''))

class XMLRPCServer(SimpleXMLRPCServer,SocketServer.ThreadingMixIn,Thread):

    allow_reuse_address = 1

    def __init__(self,RequestHandlerClass,manager):
        Thread.__init__(self)
        self.manager = manager
        self.policy = policy.get_policy()
        self._quit = 0
        addr = self.policy(policy.XMLRPC_IP), \
               self.policy(policy.XMLRPC_PORT)
        try:
            SimpleXMLRPCServer.__init__(self,addr,RequestHandlerClass,
                                        logRequests=0)
        except Exception,why:
            raise BindException,'%s:%d: %s' % (addr+(str(why),))
        self.register_instance(self.manager)

    def get_request(self):
        while not self._quit:
            try:
                ifds,ofds,efds = select.select([self],[],[],10)
            except:
                ifds,ofds,efds = [],[],[]
            if len(ifds) > 0:
                return self.socket.accept()
        return None

    def run(self):
        while not self._quit:
            try:
                self.handle_request()
            except TypeError:
                pass
        print 'xmlrpc stopped'

    def stop(self):
        self._quit = 1
        self.server_close()

class XMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def setup(self):
        SimpleXMLRPCRequestHandler.setup(self)
        self.manager = self.server.manager
        self.policy = self.server.policy
        self.id = self.policy(policy.XMLRPC_ID).split(',')

    def _dispatch(self,method,params):
        if len(params) < 1 or not params[0] in self.id:
            raise Exception('unauthorized')
        res = SimpleXMLRPCRequestHandler._dispatch(self,method,params[1:])
        if isinstance(res,CommandResponse):
            res = res.encode()
        return res

class _Method:
    def __init__(self,send,name,id=''):
        self.__send = send
        self.__name = name
        self.__id = id

    def __getattr__(self,name):
        return _Method(self.__send,"%s.%s" % (self.__name,name),self.__id)

    def __call__(self,*args):
        dict = self.__send(self.__name,(self.__id,)+args)
        res = CommandResponse()
        res.decode(dict)
        return res

class XMLRPCRequest(xmlrpclib.ServerProxy):
    def __init__(self, addr, id, transport=None, encoding='iso-8859-1', verbose=0):
        self.addr = addr
        self.__id = id
        uri = 'http://%s:%d' % self.addr
        # establish a "logical" server connection

        # get the url
        import urllib
        type, uri = urllib.splittype(uri)
        if type not in ("http", "https"):
            raise IOError, "unsupported XML-RPC protocol"
        self.__host, self.__handler = urllib.splithost(uri)
        if not self.__handler:
            self.__handler = "/RPC2"

        if transport is None:
            if type == "https":
                transport = xmlrpclib.SafeTransport()
            else:
                transport = xmlrpclib.Transport()
        self.__transport = transport

        self.__encoding = encoding
        self.__verbose = verbose

    def __request(self, methodname, params):
        # call a method on the remote server

        request = xmlrpclib.dumps(params, methodname, encoding=self.__encoding)

        response = self.__transport.request(
            self.__host,
            self.__handler,
            request,
            verbose=self.__verbose
            )

        if len(response) == 1:
            response = response[0]

        return response

    def __getattr__(self,name):
        return _Method(self.__request,name,self.__id)

if __name__ == '__main__':
    rpc = XMLRPCRequest(('127.0.0.1',19413),'xmlrpcbt')
    print rpc.listMethods()
