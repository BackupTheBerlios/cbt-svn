#!/usr/bin/python

import SocketServer
from threading import Thread
import select
import socket
import urllib
import os

from queue import QueueEntry
from BitQueue import version,BindException
import policy
from i18n import *

class WebServiceServer(SocketServer.ThreadingTCPServer,Thread):

    allow_reuse_address = 1

    def __init__(self,RequestHandlerClass,queue):
        Thread.__init__(self)
        self.queue = queue
        self.policy = policy.get_policy()
        self._quit = 0
        addr = self.policy(policy.WEBSERVICE_IP), \
               self.policy(policy.WEBSERVICE_PORT)
        try:
            SocketServer.ThreadingTCPServer.__init__(self,addr,RequestHandlerClass)
        except Exception,why:
            raise BindException,'%s:%d: %s' % (addr+(str(why),))

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
        print 'webservice stopped'

    def stop(self):
        self._quit = 1
        self.server_close()

class WebServiceRequestHandler(SocketServer.StreamRequestHandler):
    rbufsize = 0

    def setup(self):
        SocketServer.StreamRequestHandler.setup(self)
        self.queue = self.server.queue
        self.policy = self.server.policy
        self.id = self.policy(policy.WEBSERVICE_ID).split(',')

    def handle(self):
        try:
            data = self.read(5048)
            idline,cmdline = data.split('\n')
#            idline = self.rfile.readline()
#            cmdline = self.rfile.readline()
            self.handle_cmd(idline,cmdline)
        except IOError,why:
            pass
        except ValueError,why:
            print why

    def read(self,size):
        return self.connection.recv(size)

    def write(self,buf):
        return self.connection.send(buf)

    def handle_cmd(self,idline,cmdline):
        key,id = idline.split('|',1)
        if key != 'ID' or not id in self.id:
            self.handle_error('mismatch id')
            return
        cmd,args = cmdline.split('|',1)
        attr = 'do_%s' % cmd
        if hasattr(self,attr):
            if self.policy(policy.WEBSERVICE_+cmd.lower()):
                getattr(self,attr)(args)
            else:
                self.handle_noperm(cmd.upper())
        else:
            self.handle_error('unknown command %s in WebServiceRequestHandler' % cmd)
            return

    def feedback(self,msg,type='Feedback'):
        self.write('%s\n%s' % (type,msg))

    def handle_error(self,msg,cmd=None):
        if cmd:
            msg = '%s,%s' % (cmd,msg)
        self.feedback('Error=%s' % msg)

    def handle_noperm(self,cmd):
        self.handle_error('permission denied',cmd=cmd)

    def handle_notimpl(self,cmd):
        self.handle_error('not implemented',cmd=cmd)

    def do_CLOSE(self,args):
        self.handle_notimpl('CLOSE')

    def do_QUERY(self,args):
        if not args:
            fields = QueueEntry.default_fields
        else:
            fields = args.split(',')
        fields.append('infohash')

        header = []
        nf = []
        for field in fields:
            if not field in QueueEntry.all_fields:
                self.handle_error('unknown field %s' % field,cmd='QUERY')
                return
            header.append(QueueEntry.header_fields[field])

        reply = ''
        for j in self.queue.jobs():
            entry = []
            for field in fields:
                entry.append(str(j.get(field)))
            reply += '|'.join(entry)+'\n'
        self.feedback(reply,type='|'.join(header))

    def do_ADD(self,args):
        reply = self.queue.add_url(args)
        if reply:
            self.handle_error(reply,cmd='ADD')
        else:
            self.feedback('OK')

    def do_DELETE(self,args):
        if args == 'COMPLETED':
            for j in self.queue.jobs():
                if j.state in [STATE_FINISHED,STATE_SEEDING]:
                    reply = self.queue.remove(j)
                    if reply:
                        self.handle_error(reply,cmd='DELETE')
                        return
        else:
            item = self.queue.job(args)
            reply = self.queue.remove(item)
            if reply:
                self.handle_error(reply,cmd='DELETE')
                return
        self.feedback('OK')

    def do_RESUME(self,args):
        item = self.queue.job(args)
        if not item:
            self.handle_error('not found',cmd='RESUME')
            return
        self.queue.resume(item)
        self.feedback('OK')

    def do_PAUSE(self,args):
        item = self.queue.job(args)
        if not item:
            self.handle_error('not found',cmd='PAUSE')
            return
        self.queue.resume(item)
        self.queue.pause(item)
        self.feedback('OK')

    def do_QUEUE(self,args):
        item = self.queue.job(args)
        if not item:
            self.handle_error('not found',cmd='QUEUE')
            return
        self.queue.pause(item)
        self.queue.resume(item)
        self.feedback('OK')

    def do_VERSION(self,args):
        self.feedback(version,type='Version')

    def do_GSET(self,args):
        ret=''
        setting=urllib.unquote_plus(args)
        #print setting
        key,value=setting.split('=',1)
        self.policy.update(key.strip(),value.strip())
        ret = ret + key + ' = ' + value
        self.policy.save()
        self.feedback(ret)
        
class WebServiceRequest:
    def __init__(self,addr,id):
        self.addr = addr
        self.id = id

    def _request(self,msg):
        self.socket = socket.socket()
        self.socket.connect(self.addr)
        self.socket.send('ID|%s\n%s' % (self.id,msg))
        reply = self.socket.recv(10240)
        self.socket.close()
        return self._decode(reply)

    def _decode(self,reply):
        try:
            data = reply.split('\n',1)
            key,value = data
        except ValueError:
            return data,''
        return key,value

    def query(self,fields=QueueEntry.default_fields):
        request = 'QUERY|%s' % ','.join(fields)
        header,lines = self._request(request)
        if header == 'Feedback':
            return lines
        header = header.split('|')
        values = []
        lines = lines.strip().split('\n')
        for line in lines:
            pairs = map(None,header,line.split('|'))
            item = {}
            for key,value in pairs:
                item[key] = value
            values.append(item)
        return header,values

    def add(self,url):
        request = 'ADD|%s' % url
        header,lines = self._request(request)
        return header,lines

    def gset(self,args):
        all_lines=''
        request = 'GSET|%s'% args
        urllib.quote_plus(request)
        header, lines = self._request(request)
	return header, lines
 
class WebInterface:
    def __init__(self):
        self.policy = policy.get_policy()
        self.addr = (self.policy(policy.WEBSERVICE_IP),
                     self.policy(policy.WEBSERVICE_PORT))

    def process(self,command,args=[]):
        self.request = WebServiceRequest(self.addr,
                                         self.policy(policy.WEBSERVICE_ID))
        attr = 'do_%s' % command
        if hasattr(self,attr):
            ret = getattr(self,attr)(args)
        else:
            ret = 'unknown command %s in WebInterface' % command
        return ret

    def do_query(self,args):
        try:
            reply = self.request.query()
            header,values = reply
        except ValueError:
            return str(reply)
        except socket.error,why:
            return "Socket error - problem connecting to web service"
        except Exception,why:
            return str(why)

        #for item in values:
        #    print '%(Title)s\n\t%(Progress)6s %(DL Speed)9s %(UL Speed)9s %(#Seeds)6s %(#Peers)6s %(BT Status)-10s' % item
        return values

    def do_add(self,args):
        if len(args) != 1:
            print 'an argument required'
            return

        url = args[0]
        if url.find(':/') == -1:
            url = os.path.abspath(url)
        url = urllib.quote(url)
        try:
            header,lines = self.request.add(url)
        except socket.error,why:
            return "Socket error - problem connecting to web service"
        except Exception,why:
            return str(why)

    def do_gset(self,args):
        if len(args) < 1:
            print 'an argument required'
            return
        for arg in args:
            try:
                header,lines = self.request.gset(arg)
            except socket.error,why:
                return "Socket error - problem connecting to web service"
            except Exception,why:
                return str(why)
 
            
        
