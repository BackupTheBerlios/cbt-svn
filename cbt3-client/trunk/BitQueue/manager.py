#!/usr/bin/python

import cmd,os,time,sys
import socket
import types
from urlparse import urlparse,urlunparse
from threading import Event
import optparse
from shlex import shlex

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import policy
import alias
from BitQueue import version
from BitCrawler.aurllib import urlopen
from html2text import html2text
from log import get_logger
from scheduler import Scheduler
from webservice import WebServiceServer,WebServiceRequestHandler
from xmlrpc import XMLRPCServer,XMLRPCRequestHandler,XMLRPCRequest, \
                   CommandResponse
from i18n import *
from queue import QueueEntry,bdecode,bencode,sha
from launchmanycore import LaunchManyThread
from scrape import get_scrape_by_metadata

def format_time(s):
    if s < 0:
        return '-'
    return time.ctime(s)

class OutputHandler:
    def __init__(self,cb_restart=None):
        self.policy = policy.get_policy()
        self.cb_restart = cb_restart

    def error(self,s):
        print s

    def debug(self,s):
        if self.policy(policy.DEBUG_LEVEL) > 0:
            print s

    def message(self,s):
        print s

    def exception(self,s):
        print 'EXCEPTION:'
        print s

    def restart(self):
        if self.cb_restart:
            self.cb_restart()

class UnknownOptionError(optparse.OptParseError):
    pass

class StandardOptionError(optparse.OptParseError):
    pass

class Option(optparse.Option):
    def take_action (self, action, dest, opt, value, values, parser):
        if action == 'help':
            raise StandardOptionError,parser.format_help()
        elif action == 'version':
            raise StandardOptionError,parser.version
        else:
            return optparse.Option.take_action(self,action,dest,opt,value,values,parser)
        return 1

STD_HELP_OPTION = Option("-h", "--help",
                         action="help",
                         help="show this help message and exit")

class OptionParser(optparse.OptionParser):
    def __init__(self,*args,**kw):
        apply(optparse.OptionParser.__init__,(self,)+args,kw)
        self._error = None
        self.wordchars = [chr(i) for i in range(33,256)]
        self.wordchars.remove('"')
        self.wordchars.remove("'")

    def is_error(self):
        return self._error

    def get_error(self):
        return self._error

    def parse_args(self,args=None,values=None):
        self._error = None
        try:
            options,args = optparse.OptionParser.parse_args(self,args,values)
        except (StandardOptionError,UnknownOptionError,ValueError),why:
            self._error = why
            options,args = None,()
        return options,args

    def error(self,msg):
        raise UnknownOptionError,msg

    def _extract_args(self,args):
        lex = shlex(StringIO(args))
        lex.whitespace_split = True
        lex.commenters = ''
        lex.wordchars = self.wordchars
        largs = []
        while 1:
            token = lex.get_token()
            if not token:
                break
            if token[0] in ['\'','"']:
                quote = token[0]
                if token.endswith(quote):
                    token = token[1:-1]
            largs.append(token)
        return largs

    def _get_args(self,args):
        if args is None:
            args = []
        if type(args) in types.StringTypes:
            args = self._extract_args(args)
        else:
            args = args[:]
        return args

class Manager:
    def __init__(self,cb_quit):
        self.cb_quit = cb_quit
        self.out = OutputHandler(self.cb_restart)

        self.policy = policy.get_policy()
        self.policy.set_handler(self.cb_policy_updated)

        self.alias = alias.get_alias()
        self.alias.set_handler(self.cb_alias_updated)

        minport = self.policy(policy.MIN_PORT)
        maxport = self.policy(policy.MAX_PORT)
        maxport = max(minport,maxport)
        args = ['--minport',minport,
                '--maxport',maxport,
                '--max_upload_rate',self.policy(policy.MAX_UPLOAD_RATE),
                '--max_download_rate',self.policy(policy.MAX_DOWNLOAD_RATE)]
        self.controller = LaunchManyThread(self.out,args,self.cb_ban)
        self.queue = Scheduler(self.controller,self.cb_dispatch,self.cb_error)
        self.log = get_logger()

        try:
            from BitQueue import ip2cc
            self.ipdb = ip2cc.CountryByIP(self.policy.get_path(policy.IP2CC_FILE))
        except Exception,why:
            self.log.warn('failed to open %s: %s\n' % \
                          (policy.IP2CC_FILE,str(why)))
            self.ipdb = []

        self.allow_acl = policy.ACL(self.policy(policy.ALLOW_ACL),self.ipdb)
        self.deny_acl = policy.ACL(self.policy(policy.DENY_ACL),self.ipdb)
        self.order_acl = self.policy(policy.ORDER_ACL).split(',')
        self.max_last_banned = self.policy(policy.MAX_LAST_BANNED)
        self.last_banned = []

        self.init_option_parser()

    def init_option_parser(self):
        self.parser = {}

        add = self.get_parser('add','[options] file|url')
        add.add_option('-r','--referer',
                       dest='referer',default=None,
                       help='specify referer')

        alias = self.get_parser('alias','[options] [group.name group.name ...] [value]')
        alias.add_option('-g','--group',
                         action='store_true',dest='group',default=0,
                         help='show group')
        alias.add_option('-s','--set',
                         action='store_true',dest='set',default=0,
                         help='add/update specified alias')
        alias.add_option('-e','--execute',
                         action='store_true',dest='execute',default=0,
                         help='execute specified alias')
        alias.add_option('-r','--remove',
                         action='store_true',dest='remove',default=0,
                         help='remove specified alias')

        bw = self.get_parser('bw','')
        detail = self.get_parser('detail','id')
        gget = self.get_parser('gget','[key]')
        gset = self.get_parser('gset','key value')
        hold = self.get_parser('hold','id1 id2 ...')
        iget = self.get_parser('iget','id [key]')
        ip = self.get_parser('ip','ip|name')
        iset = self.get_parser('iset','id key value')
        kill = self.get_parser('kill','')
        last_banned = self.get_parser('last_banned','[n]')
        lget = self.get_parser('lget','id [key]')
        list = self.get_parser('list','[waiting|running|seeding|finished]')
        lset = self.get_parser('lset','id key value')

        meta = self.get_parser('meta','[options] id|file|url')
        meta.add_option('-r','--referer',
                        dest='referer',default=None,
                        help='specify referer')

        pause = self.get_parser('pause','id1 id2 ...')
        quit = self.get_parser('quit','')

        scrape = self.get_parser('scrape','[options] id|file|url')
        scrape.add_option('-r','--referer',
                          dest='referer',default=None,
                          help='specify referer')

        reannounce = self.get_parser('reannounce','[options] id1 id2 ...')
        reannounce.add_option('-a','--all',
                              action='store_true',dest='all',default=0,
                              help='reannounce all items')

        remove = self.get_parser('remove','id1 id2 ...')
        resched = self.get_parser('resched','')
        resume = self.get_parser('resume','id1 id2 ...')
        savequeue = self.get_parser('savequeue','')
        spew = self.get_parser('spew','id')
        superseed = self.get_parser('superseed','id')
        unhold = self.get_parser('unhold','id1 id2 ...')
        version = self.get_parser('version','')

        wget = self.get_parser('wget')
        wget.add_option('-s','--source',
                        action='store_true',dest='source',default=0,
                        help='show source')
        wget.add_option('-r','--referer',
                        dest='referer',default=None,
                        help='specify referer')

        wpost = self.get_parser('wpost')
        wpost.add_option('-s','--source',
                         action='store_true',dest='source',default=0,
                         help='show source')
        wpost.add_option('-r','--referer',
                         dest='referer',default=None,
                         help='specify referer')

    def get_parser(self,prog,usage=None):
        if not self.parser.has_key(prog):
            if not usage is None:
                usage = 'usage: %s %s' % (prog,usage)
            self.parser[prog] = OptionParser(prog=prog,usage=usage,
                                             option_class=Option,
                                             add_help_option=0)
            self.parser[prog].add_option(STD_HELP_OPTION)
        return self.parser[prog]

    def get_usage(self,prog):
        attr = 'do_'+prog
        if not hasattr(self,attr):
            return '*** No help on %s' % prog
        usage = getattr(self,attr).__doc__
        if self.parser.has_key(prog):
            usage += '\n'+self.get_parser(prog).format_help()
        return usage.rstrip()

    def cb_ban(self,ip):
        result = True
        for acl in self.order_acl:
            acl = acl.strip().lower()
            if acl not in ['allow','deny']:
                continue
            o = getattr(self,'%s_acl' % acl)
            if o.exists(ip):
                result = (acl == 'deny')
                break
        if result:
            self.last_banned.append(ip)
            self.last_banned = self.last_banned[-self.max_last_banned:]

    def cb_alias_updated(self,key):
        pass

    def cb_policy_updated(self,key):
        if key == policy.DEFAULT_SOCKET_TIMEOUT:
            import timeoutsocket
            timeoutsocket.setDefaultSocketTimeout(self.policy(key))
            del timeoutsocket
        elif key == policy.MAX_UPLOAD_RATE:
            self.queue.calculate_upload_rate()
            #self.controller.set_upload_rate(self.policy(key))
        elif key == policy.MAX_DOWNLOAD_RATE:
            self.queue.calculate_download_rate()
            #self.controller.set_download_rate(self.policy(key))
        elif key == policy.ALLOW_ACL:
            self.allow_acl = policy.ACL(self.policy(key),self.ipdb)
        elif key == policy.DENY_ACL:
            self.deny_acl = policy.ACL(self.policy(key),self.ipdb)
        elif key == policy.ORDER_ACL:
            self.order_acl = self.policy(key).split(',')
        elif key == policy.MAX_LAST_BANNED:
            self.max_last_banned = self.policy(key)
        elif key == policy.DEBUG_LEVEL:
            self.apply_debug_level(self.policy(key))

    def cb_error(self,msg):
        self.out.error(msg)

    def cb_restart(self):
        try:
            self.controller.stop()
            self.queue.stop()
            self.webservice.stop()
            self.xmlrpc.stop()
            self.policy.save()

            del self.controller
            del self.queue
            del self.webservice
            del self.xmlrpc
        except Exception,why:
            pass

        minport = self.policy(policy.MIN_PORT)
        maxport = self.policy(policy.MAX_PORT)
        maxport = max(minport,maxport)
        args = ['--minport',minport,
                '--maxport',maxport,
                '--max_upload_rate',self.policy(policy.MAX_UPLOAD_RATE),
                '--max_download_rate',self.policy(policy.MAX_DOWNLOAD_RATE)]

        self.controller = LaunchManyThread(OutputHandler(self.cb_restart),args)
        self.queue = Scheduler(self.controller,self.cb_dispatch,self.cb_error)

        self.init()
        self.start()

    def cb_dispatch(self,item,cb_finished,cb_failed):
        item.cb_finished = cb_finished
        item.cb_failed = cb_failed
        self.controller.add(item)

    def apply_debug_level(self,level):
        import httplib
        if level >= 4:
            httplib.HTTPConnection.debuglevel = 1
        else:
            httplib.HTTPConnection.debuglevel = 0
        self.log.set_debug_level(level)

    def init(self):
        try:
            self.webservice = WebServiceServer(WebServiceRequestHandler,
                                               self.queue)
            self.xmlrpc = XMLRPCServer(XMLRPCRequestHandler,
                                       self)
        except Exception,why:
            raise Exception,why

    def start(self):
        self.webservice.start()
        self.xmlrpc.start()
        self.controller.start()
        self.queue.start()

    def do_help(self,arg):
        return CommandResponse({'text':self.get_usage(arg)})

    def do_version(self,line=None):
        parser = self.get_parser('version')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        return CommandResponse({'version':version})

    def do_shell(self,line=None):
        import popen2
        fp = popen2.Popen4(line,0)
        fp.wait()
        return CommandResponse({'text':fp.fromchild.read()})

    def do_last_banned(self,line=None):
        '''show last banned ip'''
        parser = self.get_parser('last_banned')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        line = args[0]

        try:
            n = int(line)
        except ValueError:
            n = self.max_last_banned
        info = []
        for ip in self.last_banned[-n:]:
            try:
                cc,netname = self.ipdb[line].split(':',1)
            except:
                cc,netname = 'XX','Unknown'
            info.append({'ip':ip,'cc':cc,'netname':netname})
        return CommandResponse(info)

    def do_add(self,line=None):
        '''add new torrent'''
        parser = self.get_parser('add')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        file = args[0]

        if file.find('://') == -1:
            file = os.path.realpath(file)
        try:
            result = self.queue.add_url(file,referer=options.referer)
        except Exception,why:
            #import traceback
            #traceback.print_exc()
            return CommandResponse(error=str(why))
        if result:
            return CommandResponse(error=result)
        return CommandResponse()

    def do_remove(self,line=None):
        '''remove given torrent out of queue'''
        parser = self.get_parser('remove')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        for id in args:
            item = self.queue.job(id)
            if not item:
                return CommandResponse(error='%s not found' % id)
            self.queue.remove(item)
        return CommandResponse()

    def do_pause(self,line=None):
        '''put the specified torrent in pause state'''
        parser = self.get_parser('pause')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        for id in args:
            item = self.queue.job(id)
            if not item:
                return CommandResponse(error='%s not found' % id)
            self.queue.pause(item)
        return CommandResponse()

    def do_resume(self,line=None):
        '''resume paused torrent'''
        parser = self.get_parser('resume')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        for id in args:
            item = self.queue.job(id)
            if not item:
                return CommandResponse(error='%s not found' % id)
            self.queue.resume(item)
        return CommandResponse()

    def do_hold(self,line=None):
        '''temporarily stop downloading the specified torrent, states are still keeping in memory'''
        parser = self.get_parser('hold')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        for id in args:
            item = self.queue.job(id)
            if not item:
                return CommandResponse(error='%s not found' % id)
            self.queue.hold(item)
        return CommandResponse()

    def do_unhold(self,line=None):
        '''continue downloading the stopped torrent'''
        parser = self.get_parser('unhold')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        for id in args:
            item = self.queue.job(id)
            if not item:
                return CommandResponse(error='%s not found' % id)
            self.queue.unhold(item)
        return CommandResponse()

    def do_gset(self,line=None):
        '''set global policy'''
        parser = self.get_parser('gset')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        try:
            key,value = args
        except ValueError,why:
            return CommandResponse(error=str(why))
        self.policy.update(key,value)
        self.policy.save()
        return CommandResponse()

    def do_gget(self,line=None):
        '''get global policy'''
        parser = self.get_parser('gget')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        line = args[0]

        ret = []
        try:
            value = self.policy(line)
            if value == None:
                raise ValueError
            ret.append((line,str(value)))
        except ValueError,why:
            gkeys = self.policy.keys()
            gkeys.sort()
            for key in gkeys:
                ret.append({'key':str(key),'value':str(self.policy(key))})
        return CommandResponse(ret)

    def do_lset(self,line=None):
        '''set local policy'''
        parser = self.get_parser('lset')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        try:
            jid,key,value = args,
        except ValueError,why:
            return CommandResponse(error=str(why))
        j = self.queue.job(jid)
        if not j:
            return CommandResponse(error='%s not found' % jid)
        lpol = j.get_policy()
        lpol.update(key,value)
        return CommandResponse()

    def do_lget(self,line=None):
        '''get local policy'''
        parser = self.get_parser('lset')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if len(args) < 1:
            return CommandResponse(error='need id')
        j = self.queue.job(args[0])
        if not j:
            return CommandResponse(error='%s not found' % args[0])
        lpol = j.get_policy()
        ret = []
        try:
            value = lpol(line)
            if value == None:
                raise ValueError
            ret.append({'key':line,'value':str(value)})
        except ValueError,why:
            lkeys = lpol.keys()
            lkeys.sort()
            for key in lkeys:
                ret.append({'key':str(key),'value':str(lpol(key))})
        return CommandResponse(ret)

    def do_iset(self,line=None):
        '''set an item attribute'''
        parser = self.get_parser('iset')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if len(args) < 3:
            return CommandResponse(error='need an id, an attribute and a value')
        id,attr,value = args
        j = self.queue.job(id)
        if not j:
            return CommandResponse(error='%s not found' % id)
        if not hasattr(j,attr):
            return CommandResponse(error='%s not found' % attr)
        atype = type(getattr(j,attr))
        try:
            if atype in types.StringTypes:
                value = str(value)
            elif atype == types.IntType:
                value = int(value)
            elif atype == types.LongType:
                value = long(value)
            elif atype == types.FloatType:
                value = float(value)
            else:
                return CommandResponse(error='unable to change %s' % str(atype))
        except Exception,why:
            return CommandResponse(error=str(why))
        #resume = 0
        #if j.state in [STATE_RUNNING,STATE_SEEDING]:
        #    self.queue.pause(j)
        #    resume = 1
        setattr(j,attr,value)
        #if resume:
        #    self.queue.resume(j)
        #self.queue.save()
        return CommandResponse()

    def do_iget(self,line=None):
        '''get item attributes'''
        parser = self.get_parser('iget')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if len(args) < 1:
            return CommandResponse(error='need an id and an optional attribute')
        try:
            id,attr = args
            attrs = [attr]
        except ValueError:
            id,attrs = args[0],QueueEntry.modifiable_vars
        j = self.queue.job(id)
        if not j:
            return CommandResponse(error='%s not found' % id)
        ret = []
        for attr in attrs:
            if not hasattr(j,attr):
                return CommandResponse(error='%s not found' % attr)
            ret.append({'key':attr,'value':str(getattr(j,attr))})
        return CommandResponse(ret)

    def do_list(self,line=None):
        '''list torrent queue'''
        parser = self.get_parser('list')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if args:
            accept_state = args
        else:
            accept_state = [STATE_WAITING,STATE_RUNNING,STATE_FINISHED,STATE_SEEDING,STATE_PAUSED,STATE_HOLDED]
        ret = []
        for j in self.queue.jobs():
            data = j.get()
            if not data['btstatus'] in accept_state:
                continue
            title = data['title']
            quoted_title = ''
            for c in title:
                if ord(c) < 32 or ord(c) > 127:
                    c = '?'
                quoted_title += c
            data['title'] = quoted_title
            data['dlsize'] = data['dlsize'].split()[0]
            data['totalsize'] = data['totalsize'].split()[0]
            data['dlspeed'] = data['dlspeed'].split()[0]
            data['ulspeed'] = data['ulspeed'].split()[0]
            data['activity'] = j.activity
            ret.append(data)
        return CommandResponse(ret)

    def do_bw(self,line=None):
        '''Show total upload / download rates'''
        parser = self.get_parser('bw')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        dlspeed = 0
        ulspeed = 0
        sdspeed = 0
        for j in self.queue.jobs():
            data = j.get()
            dlspeed += float(data['dlspeed'].split()[0])
            ulspeed += float(data['ulspeed'].split()[0])
            if j.state == STATE_SEEDING:
                sdspeed += float(data['ulspeed'].split()[0])
        max_dl = float(self.policy(policy.MAX_DOWNLOAD_RATE))
        max_ul = float(self.policy(policy.MAX_UPLOAD_RATE))
        max_sd = float(self.policy(policy.MAX_SEED_RATE))
        return CommandResponse({'down_rate':dlspeed,
                                'up_rate':ulspeed,
                                'seed_rate':sdspeed,
                                'max_down':max_dl,
                                'max_up':max_ul,
                                'max_seed':max_sd,
                                'down_percent':dlspeed/max(1,max_dl),
                                'up_percent':ulspeed/max(1,max_ul),
                                'seed_percent':sdspeed/max(1,max_sd)})
            
    def do_spew(self,line=None):
        '''display spew of given torrent id
Clients:
	S		Shad0w
	S Plus		Shad0w Plus
	BT		BitTornado
	BT M		BitTornado Launch Many
	BTQ		BTQueue
	Az		Azureus
	BS		BitSpirit
	UPnP		Universal Plug and Play
	BC		BitComet
	TBT		TurboBT
	G3		G3 Torrent
	BT Plus		BitTorrent Plus!
	Deadman		Deadman
	libt		libtorrent
	TS		TorrentStorm
	MT		MoonlightTorrent
	Snark		Snark
	BTugaXP		BTugaXP
	SBT		SimpleBT
	XT		XanTorrent
	Exp		Experimental
	Generic		Generic BitTorrent'''
        parser = self.get_parser('spew')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        line = args[0]

        if not line:
            return CommandResponse(error='need id')
        j = self.queue.job(line)
        if not j:
            return CommandResponse(error='%s not found' % line)
        spew = j.get_spew()
        ret = []
        for i in spew:
            var = {}
            var.update(i)
            try:
                var['cc'],var['netname'] = self.ipdb[i['ip']].split(':',1)
            except (IndexError,TypeError,KeyError,AssertionError,ValueError):
                var['cc'],var['netname'] = 'XX','Unknown'
            var['client'] = var['client'][:12]
            var['netname'] = var['netname']
            ret.append(var)
        return CommandResponse(ret)

    def do_ip(self,line=None):
        '''display full information of given IP'''
        parser = self.get_parser('ip')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        line = args[0]

        try:
            ip = socket.gethostbyname(line)
        except:
            ip = line
        try:
            cc,netname = self.ipdb[ip].split(':',1)
        except (IndexError,TypeError,KeyError,AssertionError,ValueError):
            cc,netname = 'XX','Unknown'
        fqdn = socket.getfqdn(line)
        if line == fqdn:
            fqdn = 'not registered'
        return CommandResponse({'ip':ip,'fqdn':fqdn,'cc':cc,'netname':netname})

    def do_meta(self,line=None):
        '''display all metadata of given torrent id'''
        parser = self.get_parser('meta')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args:
            return CommandResponse(error='need id or path or url')
        line = args[0]
        j = self.queue.job(line)
        if j:
            meta = j.get_meta()
            detail = j.get()
            info = meta['info']
        else:
            try:
                #from scheduler import urlopen as _urlopen
                from queue import sha,bdecode
                if line.find('://') == -1:
                    line = os.path.realpath(line)
                meta = bdecode(urlopen(line,referer=options.referer).read())
                info = meta['info']
                detail = {'infohash':sha(bencode(info)).hexdigest()}
            except ValueError:
                return CommandResponse(error='invalid metadata')
            except Exception,why:
                return CommandResponse(error=str(why))

        ret = {'infohash':detail['infohash']}
        for key in meta.keys():
            if not key in ['info','name','length','files','resume']:
                ret[key] = str(meta[key])
        files = []
        if info.has_key('length'):
            files.append({'length':info['length'],'name':info['name']})
        else:
            for i in info['files']:
                files.append({'length':i['length'],
                              'name':apply(os.path.join,[info['name']]+i['path'])})
        ret['files'] = files
        return CommandResponse(ret)

    def do_scrape(self,line=None):
        '''display scape of given torrent id'''
        parser = self.get_parser('scrape')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args:
            return CommandResponse(error='need id or path or url')
        line = args[0]
        meta = None
        j = self.queue.job(line)
        if j:
            meta = j.get_meta()
        else:
            try:
                #from scheduler import urlopen as _urlopen
                from queue import sha,bdecode
                if line.find('://') == -1:
                    line = os.path.realpath(line)
                meta = bdecode(urlopen(line,referer=options.referer).read())
            except ValueError:
                return CommandResponse(error='invalid metadata')
            except Exception,why:
                return CommandResponse(error=str(why))
        if not meta:
            return CommandResponse(error='%s not found' % line)

        seeders,leechers = get_scrape_by_metadata(meta)
        return CommandResponse({'seeders':seeders,
                                'leechers':leechers})

    def do_detail(self,line=None):
        '''display detail of given torrent id'''
        parser = self.get_parser('detail')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())
        id = args[0]

        if not id:
            return CommandResponse(error='need id')
        j = self.queue.job(id)
        if not j:
            return CommandResponse(error='%s not found' % id)
        data = j.get()
        data['title'] = data['title']
        data['dlsize'] = data['dlsize'].split()[0]
        data['totalsize'] = data['totalsize'].split()[0]
        data['dlspeed'] = data['dlspeed'].split()[0]
        data['ulspeed'] = data['ulspeed'].split()[0]
        data['added_time'] = format_time(data['added_time'])
        data['started_time'] = format_time(data['started_time'])
        data['finished_time'] = format_time(data['finished_time'])
        data['stopped_time'] = format_time(data['stopped_time'])
        return CommandResponse(data)

    def do_reannounce(self,line=None):
        '''reannounce now'''
        parser = self.get_parser('reannounce')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args and not options.all:
            return CommandResponse(error='need id')
        if args:
            for id in args:
                j = self.queue.job(id)
                if not j:
                    return CommandResponse(error='%s not found' % id)
                if j.dow:
                    j.dow.reannounce()
        else:
            for j in self.queue.jobs():
                if j.dow:
                    j.dow.reannounce()
        return CommandResponse()

    def do_superseed(self,line=None):
        '''turn on superseed mode'''
        parser = self.get_parser('resched')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args:
            return CommandResponse(error='need id')
        for id in args:
            j = self.queue.job(id)
            if not j:
                return CommandResponse(error='%s not found' % id)
            if j.dow:
                j.dow.set_super_seed()
        return CommandResponse()

    def do_resched(self,line=None):
        '''schedule now'''
        parser = self.get_parser('resched')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        self.queue.schedule()
        return CommandResponse()

    def do_savequeue(self,line=None):
        '''save queue immediately'''
        parser = self.get_parser('savequeue')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        self.queue.save()
        return CommandResponse()

    def do_wget(self,line=None):
        '''retrieve http content using get'''
        parser = self.get_parser('wget')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args:
            return CommandResponse(error='need url')
        try:
            content = urlopen(args[0],method='get',referer=options.referer).read()
            if options.source:
                return CommandResponse({'text':content})
            return CommandResponse({'text':html2text(content).encode('iso-8859-1')})
        except Exception,why:
            return CommandResponse(error=str(why))

    def do_wpost(self,line=None):
        '''retrieve http content using post'''
        parser = self.get_parser('wpost')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if not args:
            return CommandResponse(error='need url')
        try:
            content = urlopen(args[0],method='post',referer=options.referer).read()
            if options.source:
                return CommandResponse({'text':content})
            return CommandResponse({'text':html2text(content).encode('iso-8859-1')})
        except Exception,why:
            return CommandResponse(error=str(why))

    def do_alias(self,line=None):
        '''manipuate alias'''
        parser = self.get_parser('alias')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        if options.execute:
            if not args:
                return CommandResponse(error='need alias')
            try:
                cmd = self.alias.get(args[0],args[1:])
            except KeyError,why:
                return CommandResponse(error=str(why))
            return CommandResponse({'command':cmd})

        if options.set:
            if len(args) < 2:
                return CommandResponse(error='need alias and value')
            for key in args[:-1]:
                self.alias.set(key,args[-1])
            self.alias.save()
            return CommandResponse()

        if options.remove:
            if not args:
                return CommandResponse(error='need alias')
            for key in args:
                self.alias.remove(key)
            self.alias.save()
            return CommandResponse()

        if options.group:
            ret = []
            if not args:
                groups = self.alias.groups()
                for group in groups:
                    ret.append({'group':group})
                return CommandResponse(ret)
            keys = []
            for group in args:
                keys.extend(self.alias.keys(group=group))
            args = keys

        targets = args or self.alias.keys()
        ret = []
        try:
            for key in targets:
                ret.append({'key':key,'value':self.alias.get(key,raw=1)})
        except KeyError,why:
            return CommandResponse(error=str(why))
        return CommandResponse(ret)

    def do_quit(self,line=None):
        '''quit'''
        parser = self.get_parser('quit')
        options,args = parser.parse_args(line)
        if parser.is_error():
            return CommandResponse(error=parser.get_error())

        self.queue.save()
        self.controller.stop()
        self.queue.stop()
        self.webservice.stop()
        self.xmlrpc.stop()
        self.policy.save()
        self.cb_quit()
        return CommandResponse()

    do_exit = do_quit
    do_info = do_detail

    def default(self,line=None):
        def find_cmds(prefix):
            cmds = []
            prefix = 'do_'+prefix
            for attr in dir(self):
                if attr.startswith(prefix):
                    cmds.append(attr)
            return cmds
        try:
            cmd,args = line.split(' ',1)
            args = args.strip()
        except ValueError:
            cmd,args = line,''
        if self.alias.has_key(cmd):
            return self.do_alias('-e %s' % line)
        cmds = find_cmds(cmd)
        lcmds = len(cmds)
        if lcmds == 0:
            return CommandResponse(error='*** Unknown syntax: %s' % line)
        elif lcmds > 1:
            return CommandResponse(error='*** Ambiguous command: %s' % ' '.join([c[3:] for c in cmds]))
        else:
            return CommandResponse({'command':'%s %s' % (cmds[0][3:],args)})

class Daemon:
    def __init__(self):
        self.manager = Manager(self.cb_quit)
        self._quit = Event()

    def cb_quit(self):
        self.do_quit()

    if sys.platform == 'win32':
        def daemonize(self,stdin='/dev/null',stdout='/dev/null',stderr='/dev/null'):
            pass
    else:
        def daemonize(self,stdin='/dev/null',stdout=None,stderr=None):
            try:
                self.manager.init()
            except Exception,why:
                #import traceback
                #exc = ''.join(apply(traceback.format_exception,sys.exc_info()))
                #self.manager.log.error(exc)
                print why
                sys.exit(1)

            stdout = stdout or self.manager.policy(policy.DAEMON_STDOUT) or '/dev/null'
            stderr = stdout or self.manager.policy(policy.DAEMON_STDERR) or '/dev/null'
            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)
            except OSError,e:
                print 'fork #1 failed: (%d) %s' % (e.errno,e.strerror)
                sys.exit(1)

            os.setsid()

            try:
                pid = os.fork()
                if pid > 0:
                    sys.exit(0)
            except OSError,e:
                print 'fork #2 failed: (%d) %s' % (e.errno,e.strerror)
                sys.exit(1)

            si = open(stdin,'r')
            so = open(stdout,'a+')
            se = open(stderr,'a+',0)
            os.dup2(si.fileno(),sys.stdin.fileno())
            os.dup2(so.fileno(),sys.stdout.fileno())
            os.dup2(se.fileno(),sys.stderr.fileno())

            self.manager.start()
            self._quit.wait()

    def do_quit(self):
        self._quit.set()

class Cbt:
    def __init__(self):
        self.m = Manager(self.cb_quit)

        try:
            self.m.init()
        except Exception,why:
            print why
            sys.exit(1)

        self.m.start()

    def cb_quit(self):
        pass

class Console(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = '>>> '
        self.manager = Manager(self.cb_quit)

    def cb_quit(self):
        import sys
        sys.stdin.close()

    def mainloop(self):
        try:
            self.manager.init()
            self.manager.start()
            self.cmdloop()
        except KeyboardInterrupt:
            pass
        except ValueError:
            import traceback
            exc = ''.join(apply(traceback.format_exception,sys.exc_info()))
            self.manager.log.error(exc)
        except Exception,why:
            import traceback
            exc = ''.join(apply(traceback.format_exception,sys.exc_info()))
            self.manager.log.error(exc)
            print exc,
        self.do_quit()

    def emptyline(self):
        self.do_list(' '.join([STATE_RUNNING,STATE_SEEDING]))

    def do_help(self,arg):
        if not arg:
            return cmd.Cmd.do_help(self,arg)
        print '%(text)s' % self.manager.do_help(arg).getreply()

    def do_version(self,line=None):
        res = self.manager.do_version(line)
        if res.geterror():
            print res.geterror()
            return
        print '%(version)s' % res.getreply()

    def do_shell(self,line=None):
        res = self.manager.do_shell(line)
        print '%(text)s' % res.getreply()

    def do_last_banned(self,line=None):
        '''show last banned ip'''
        res = self.manager.do_last_banned(line)
        if res.geterror():
            print res.geterror()
            return
        for data in res.getreply():
            print '%(ip)-16s %(cc)-2s %(netname)s' % data

    def do_add(self,line=None):
        '''add new torrent'''
        res = self.manager.do_add(line)
        if res.geterror():
            print res.geterror()

    def do_remove(self,line=None):
        '''remove given torrent out of queue'''
        res = self.manager.do_remove(line)
        if res.geterror():
            print res.geterror()

    def do_pause(self,line=None):
        '''put the specified torrent in pause state'''
        res = self.manager.do_pause(line)
        if res.geterror():
            print res.geterror()

    def do_resume(self,line=None):
        '''resume paused torrent'''
        res = self.manager.do_resume(line)
        if res.geterror():
            print res.geterror()

    def do_hold(self,line=None):
        '''temporarily stop downloading the specified torrent, states are still keeping in memory'''
        res = self.manager.do_hold(line)
        if res.geterror():
            print res.geterror()

    def do_unhold(self,line=None):
        '''continue downloading the stopped torrent'''
        res = self.manager.do_unhold(line)
        if res.geterror():
            print res.geterror()

    def do_gset(self,line=None):
        '''set global policy'''
        res = self.manager.do_gset(line)
        if res.geterror():
            print res.geterror()

    def do_gget(self,line=None):
        '''get global policy'''
        res = self.manager.do_gget(line)
        if res.geterror():
            print res.geterror()
            return
        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_lset(self,line=None):
        '''set local policy'''
        res = self.manager.do_lset(line)
        if res.geterror():
            print res.geterror()

    def do_lget(self,line=None):
        '''get local policy'''
        res = self.manager.do_lget(line)
        if res.geterror():
            print res.geterror()
            return
        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_iset(self,line=None):
        '''set an item attribute'''
        res = self.manager.do_iset(line)
        if res.geterror():
            print res.geterror()

    def do_iget(self,line=None):
        '''get item attributes'''
        res = self.manager.do_iget(line)
        if res.geterror():
            print res.geterror()
            return
        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_list(self,line=None):
        '''list torrent queue'''
        res = self.manager.do_list(line)
        if res.geterror():
            print res.geterror()
            return
        for data in res.getreply():
            print '%(id)2s %(title)-20s %(progress)6s %(dlsize)7s/%(totalsize)-7s ' % data,
            print '%(eta)8s %(dlspeed)4s %(ulspeed)4s ' % data,
            print '%(seeds)6s %(peers)6s %(btstatus)10s %(ratio)6s' % data,
            print '%(activity)s' % data

    def do_bw(self,line=None):
        '''Show total upload / download rates'''
        res = self.manager.do_bw(line)
        if res.geterror():
            print res.geterror()
            return
        data = res.getreply()
        print 'Download Speed: %(down_rate)5.1f (%(down_percent)0.1f%%)' % data
        print 'Upload Speed: %(up_rate)5.1f (%(up_percent)0.1f%%)' % data
        print 'Seed Speed: %(seed_rate)5.1f (%(seed_percent)0.1f%%)' % data
            
    def do_spew(self,line=None):
        '''display spew of given torrent id
Clients:
	S		Shad0w
	S Plus		Shad0w Plus
	BT		BitTornado
	BT M		BitTornado Launch Many
	BTQ		BTQueue
	Az		Azureus
	BS		BitSpirit
	UPnP		Universal Plug and Play
	BC		BitComet
	TBT		TurboBT
	G3		G3 Torrent
	BT Plus		BitTorrent Plus!
	Deadman		Deadman
	libt		libtorrent
	TS		TorrentStorm
	MT		MoonlightTorrent
	Snark		Snark
	BTugaXP		BTugaXP
	SBT		SimpleBT
	XT		XanTorrent
	Exp		Experimental
	Generic		Generic BitTorrent'''
        res = self.manager.do_spew(line)
        if res.geterror():
            print res.geterror()
            return

        headers = {'ip': 'IP',
                   'cc': 'CC',
                   'direction': 'D',
                   'uprate': 'U/R',
                   'downrate': 'D/R',
                   'dtotal': 'D',
                   'utotal': 'U',
                   'completed': 'C',
                   'client': 'Client',
                   'netname': 'Netname'}
        print '%(ip)-15s %(cc)2s %(direction)s %(uprate)4s %(downrate)4s %(dtotal)7s %(utotal)7s %(completed)7s %(client)-12s %(netname)s' % headers
        for data in res.getreply():
            print '%(ip)-15s %(cc)2s %(direction)s %(uprate)4s %(downrate)4s %(dtotal)7s %(utotal)7s %(completed)7s %(client)-12s %(netname)s' % data

    def do_ip(self,line=None):
        '''display full information of given IP'''
        res = self.manager.do_ip(line)
        if res.geterror():
            print res.geterror()
            return

        print '''IP: %(ip)s
FQDN: %(fqdn)s
Country: %(cc)s
NetName: %(netname)s''' % res.getreply()

    def do_meta(self,line=None):
        '''display all metadata of given torrent id'''
        res = self.manager.do_meta(line)
        if res.geterror():
            print res.geterror()
            return

        detail = res.getreply()
        print '%-20s %s' % ('infohash:',detail['infohash'])
        for key in detail.keys():
            if not key in ['infohash','files']:
                print '%-20s %s' % (key+':',str(detail[key]))
        print '%-20s' % 'files:'
        length = 0
        for i in detail['files']:
            length += i['length']
            print '%15ld %s' % (i['length'],i['name'])
        print '%-20s %ld' % ('length:',length)

    def do_scrape(self,line=None):
        '''display scrape of given torrent'''
        res = self.manager.do_scrape(line)
        if res.geterror():
            print res.geterror()
            return

        print '''Seeders: %(seeders)s
Leechers: %(leechers)s''' % res.getreply()

    def do_detail(self,line=None):
        '''display detail of given torrent id'''
        res = self.manager.do_detail(line)
        if res.geterror():
            print res.geterror()
            return

        print '''ID:                    %(id)s
Response:              %(filename)s
Info Hash:             %(infohash)s
Announce:              %(announce)s
Peer ID:               %(peer_id)s
Name:                  %(title)s
Destination:           %(dest_path)s
Size:                  %(totalsize)s
ETA:                   %(eta)s
State:                 %(btstatus)s
Progress:              %(progress)s
Downloaded/Uploaded:   %(dlsize)s/%(ulsize)s
Share Ratio:           %(ratio)s
Download/Upload Speed: %(dlspeed)s/%(ulspeed)s
Total Speed:           %(totalspeed)s
Peer Average Progress: %(peeravgprogress)s
Peers/Seeds/Copies:    %(peers)s/%(seeds)s/%(copies)0.3f
Last Error:            %(error)s
Added:                 %(added_time)s
Started:               %(started_time)s
Finished:              %(finished_time)s
Stopped:               %(stopped_time)s
''' % res.getreply()

    def do_reannounce(self,line=None):
        '''reannounce now'''
        res = self.manager.do_reannounce(line)
        if res.geterror():
            print res.geterror()
            return

    def do_superseed(self,line=None):
        '''turn on superseed mode'''
        res = self.manager.do_superseed(line)
        if res.geterror():
            print res.geterror()
            return

    def do_resched(self,line=None):
        '''schedule now'''
        res = self.manager.do_resched(line)
        if res.geterror():
            print res.geterror()
            return

    def do_savequeue(self,line=None):
        '''save queue immediately'''
        res = self.manager.do_savequeue(line)
        if res.geterror():
            print res.geterror()
            return

    def do_wget(self,line=None):
        '''retrieve http content using get'''
        res = self.manager.do_wget(line)
        if res.geterror():
            print res.geterror()
            return

        print '%(text)s' % res.getreply()

    def do_wpost(self,line=None):
        '''retrieve http content using post'''
        res = self.manager.do_wpost(line)
        if res.geterror():
            print res.geterror()
            return

        print '%(text)s' % res.getreply()

    def do_alias(self,line=None):
        '''manipuate alias'''
        res = self.manager.do_alias(line)
        if res.geterror():
            print res.geterror()
            return

        reply = res.getreply()
        if type(reply) == type({}):
            if reply.has_key('command'):
                self.onecmd('%(command)s' % reply)
            else:
                print '%(text)s' % reply
            return
        for alias in reply:
            if alias.has_key('group'):
                print '%(group)s' % alias
            else:
                print '%(key)s = %(value)s' % alias

    def do_quit(self,line=None):
        '''quit'''
        res = self.manager.do_quit(line)
        if res.geterror():
            print res.geterror()
            return

        return 1

    do_EOF = do_quit

    def default(self,line=None):
        res = self.manager.default(line)
        if res.geterror():
            print res.geterror()
            return

        command = '%(command)s' % res.getreply()
        self.onecmd(command)

#class XMLRPCConsole(cmd.Cmd):
class XMLRPCConsole:
    def __init__(self):
        #cmd.Cmd.__init__(self)
        self.prompt = '>>> '
        self.policy = policy.get_policy()
        addr = self.policy(policy.XMLRPC_IP),self.policy(policy.XMLRPC_PORT)
        id = self.policy(policy.XMLRPC_ID)
        self.manager = XMLRPCRequest(addr,id)
        self.log = get_logger()

    def mainloop(self):
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            pass
        except Exception,why:
            import traceback
            exc = ''.join(apply(traceback.format_exception,sys.exc_info()))
            self.log.error(exc)
            print exc,
        self.do_quit()

    def emptyline(self):
        self.do_list(' '.join([STATE_RUNNING,STATE_SEEDING]))

    def do_help(self,arg):
        if not arg:
            return cmd.Cmd.do_help(self,arg)
        print '%(text)s' % self.manager.do_help(arg).getreply()

    def do_version(self,line=None):
        res = self.manager.do_version(line)
        print '%(version)s' % res.getreply()

    def do_shell(self,line=None):
        res = self.manager.do_shell(line)
        print '%(text)s' % res.getreply()

    def do_last_banned(self,line=None):
        '''show last banned ip'''
        res = self.manager.do_last_banned(line)
        if res.geterror():
            print res.geterror()
            return

        for data in res.getreply():
            print '%(ip)-16s %(cc)-2s %(netname)s' % data

    def do_add(self,line=None):
        '''add new torrent'''
        res = self.manager.do_add(line)
        if res.geterror():
            print res.geterror()

    def do_remove(self,line=None):
        '''remove given torrent out of queue'''
        res = self.manager.do_remove(line)
        if res.geterror():
            print res.geterror()

    def do_pause(self,line=None):
        '''put the specified torrent in pause state'''
        res = self.manager.do_pause(line)
        if res.geterror():
            print res.geterror()

    def do_resume(self,line=None):
        '''resume paused torrent'''
        res = self.manager.do_resume(line)
        if res.geterror():
            print res.geterror()

    def do_hold(self,line=None):
        '''temporarily stop downloading the specified torrent, states are still keeping in memory'''
        res = self.manager.do_hold(line)
        if res.geterror():
            print res.geterror()

    def do_unhold(self,line=None):
        '''continue downloading the stopped torrent'''
        res = self.manager.do_unhold(line)
        if res.geterror():
            print res.geterror()

    def do_gset(self,line=None):
        '''set global policy'''
        res = self.manager.do_gset(line)
        if res.geterror():
            print res.geterror()

    def do_gget(self,line=None):
        '''get global policy'''
        res = self.manager.do_gset(line)
        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_lset(self,line=None):
        '''set local policy'''
        res = self.manager.do_lset(line)
        if res.geterror():
            print res.geterror()

    def do_lget(self,line=None):
        '''get local policy'''
        res = self.manager.do_lset(line)
        if res.geterror():
            print res.geterror()
            return

        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_iset(self,line=None):
        '''set an item attribute'''
        res = self.manager.do_iset(line)
        if res.geterror():
            print res.geterror()

    def do_iget(self,line=None):
        '''get item attributes'''
        res = self.manager.do_iget(line)
        if res.geterror():
            print res.geterror()
            return

        for data in res.getreply():
            data['key'] += ':'
            print '%(key)-20s %(value)s' % data

    def do_list(self,line=None):
        '''list torrent queue'''
        res = self.manager.do_list(line)
        if res.geterror():
            print res.geterror()
            return

        for data in res.getreply():
            print '%(id)2s %(title)-20s %(progress)6s %(dlsize)7s/%(totalsize)-7s ' % data,
            print '%(eta)8s %(dlspeed)4s %(ulspeed)4s ' % data,
            print '%(seeds)6s %(peers)6s %(btstatus)10s %(ratio)6s' % data,
            print '%(activity)s' % data

    def do_bw(self,line=None):
        '''Show total upload / download rates'''
        res = self.manager.do_bw(line)
        if res.geterror():
            print res.geterror()
            return

        data = res.getreply()
        print 'Download Speed: %(down_rate)5.1f (%(down_percent)0.1f%%)' % data
        print 'Upload Speed: %(up_rate)5.1f (%(up_percent)0.1f%%)' % data
        print 'Seed Speed: %(seed_rate)5.1f (%(seed_percent)0.1f%%)' % data
            
    def do_spew(self,line=None):
        '''display spew of given torrent id
Clients:
	S		Shad0w
	S Plus		Shad0w Plus
	BT		BitTornado
	BT M		BitTornado Launch Many
	BTQ		BTQueue
	Az		Azureus
	BS		BitSpirit
	UPnP		Universal Plug and Play
	BC		BitComet
	TBT		TurboBT
	G3		G3 Torrent
	BT Plus		BitTorrent Plus!
	Deadman		Deadman
	libt		libtorrent
	TS		TorrentStorm
	MT		MoonlightTorrent
	Snark		Snark
	BTugaXP		BTugaXP
	SBT		SimpleBT
	XT		XanTorrent
	Exp		Experimental
	Generic		Generic BitTorrent'''
        res = self.manager.do_spew(line)
        if res.geterror():
            print res.geterror()
            return

        headers = {'ip': 'IP',
                   'cc': 'CC',
                   'direction': 'D',
                   'uprate': 'U/R',
                   'downrate': 'D/R',
                   'dtotal': 'D',
                   'utotal': 'U',
                   'completed': 'C',
                   'client': 'Client',
                   'netname': 'Netname'}
        print '%(ip)-15s %(cc)2s %(direction)s %(uprate)4s %(downrate)4s %(dtotal)7s %(utotal)7s %(completed)7s %(client)-12s %(netname)s' % headers
        for data in res.getreply():
            print '%(ip)-15s %(cc)2s %(direction)s %(uprate)4s %(downrate)4s %(dtotal)7s %(utotal)7s %(completed)7s %(client)-12s %(netname)s' % data

    def do_ip(self,line=None):
        '''display full information of given IP'''
        res = self.manager.do_ip(line)
        if res.geterror():
            print res.geterror()
            return

        print '''IP: %(ip)s
FQDN: %(fqdn)s
Country: %(cc)s
NetName: %(netname)s''' % res.getreply()

    def do_meta(self,line=None):
        '''display all metadata of given torrent id'''
        res = self.manager.do_meta(line)
        if res.geterror():
            print res.geterror()
            return

        detail = res.getreply()
        print '%-20s %s' % ('infohash:',detail['infohash'])
        for key in detail.keys():
            if not key in ['infohash','files']:
                print '%-20s %s' % (key+':',str(detail[key]))
        print '%-20s' % 'files:'
        length = 0
        for i in detail['files']:
            length += i['length']
            print '%15ld %s' % (i['length'],i['name'])
        print '%-20s %ld' % ('length:',length)

    def do_scrape(self,line=None):
        '''display scrape of given torrent'''
        res = self.manager.do_scrape(line)
        if res.geterror():
            print res.geterror()
            return

        print '''Seeders: %(seeders)s
Leechers: %(leechers)s''' % res.getreply()

    def do_detail(self,line=None):
        '''display detail of given torrent id'''
        res = self.manager.do_detail(line)
        if res.geterror():
            print res.geterror()
            return

        print '''ID:                    %(id)s
Response:              %(filename)s
Info Hash:             %(infohash)s
Announce:              %(announce)s
Peer ID:               %(peer_id)s
Name:                  %(title)s
Destination:           %(dest_path)s
Size:                  %(totalsize)s
ETA:                   %(eta)s
State:                 %(btstatus)s
Progress:              %(progress)s
Downloaded/Uploaded:   %(dlsize)s/%(ulsize)s
Share Ratio:           %(ratio)s
Download/Upload Speed: %(dlspeed)s/%(ulspeed)s
Total Speed:           %(totalspeed)s
Peer Average Progress: %(peeravgprogress)s
Peers/Seeds/Copies:    %(peers)s/%(seeds)s/%(copies)0.3f
Last Error:            %(error)s
Added:                 %(added_time)s
Started:               %(started_time)s
Finished:              %(finished_time)s
Stopped:               %(stopped_time)s
''' % res.getreply()

    def do_reannounce(self,line=None):
        '''reannounce now'''
        res = self.manager.do_reannounce(line)
        if res.geterror():
            print res.geterror()
            return

    def do_superseed(self,line=None):
        '''turn on superseed mode'''
        res = self.manager.do_superseed(line)
        if res.geterror():
            print res.geterror()
            return

    def do_resched(self,line=None):
        '''schedule now'''
        res = self.manager.do_resched(line)
        if res.geterror():
            print res.geterror()
            return

    def do_savequeue(self,line=None):
        '''save queue immediately'''
        res = self.manager.do_savequeue(line)
        if res.geterror():
            print res.geterror()
            return

    def do_wget(self,line=None):
        '''retrieve http content using get'''
        res = self.manager.do_wget(line)
        if res.geterror():
            print res.geterror()
            return

        print '%(text)s' % res.getreply()

    def do_wpost(self,line=None):
        '''retrieve http content using post'''
        res = self.manager.do_wpost(line)
        if res.geterror():
            print res.geterror()
            return

        print '%(text)s' % res.getreply()

    def do_alias(self,line=None):
        '''manipuate alias'''
        res = self.manager.do_alias(line)
        if res.geterror():
            print res.geterror()
            return

        reply = res.getreply()
        if type(reply) == type({}):
            if reply.has_key('command'):
                self.onecmd('%(command)s' % reply)
            else:
                print '%(text)s' % reply
            return
        for alias in reply:
            if alias.has_key('group'):
                print '%(group)s' % alias
            else:
                print '%(key)s = %(value)s' % alias

    def do_kill(self,line=None):
        '''kill'''
        res = self.manager.do_quit(line)
        if res.geterror():
            print res.geterror()

        return 1

    def do_quit(self,line=None):
        '''detach'''
        return 1

    do_EOF = do_quit

    def default(self,line=None):
        res = self.manager.default(line)
        if res.geterror():
            print res.geterror()
            return

        command = '%(command)s' % res.getreply()
        self.onecmd(command)
