#!/usr/bin/python

import cmd,os,time
import socket
import types
from urlparse import urlparse,urlunparse

import policy
from BitQueue import version
from BitCrawler.aurllib import urlopen
from html2text import html2text
from log import get_logger
from scheduler import Scheduler
from webservice import WebServiceServer,WebServiceRequestHandler
from i18n import *
from queue import QueueEntry,bdecode,bencode,sha
from launchmanycore import LaunchManyThread

def format_time(s):
    if s < 0:
        return '-'
    return time.ctime(s)

class OutputHandler:
    def __init__(self,cb_restart=None):
        self.policy = policy.get_policy()
        self.cb_restart = cb_restart

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

#~ class Console(cmd.Cmd):
class Console:
    def __init__(self):
        #~ cmd.Cmd.__init__(self)
        self.policy = policy.get_policy()
        self.policy.set_handler(self.cb_policy_updated)
        from random import randrange
        minport = self.policy(policy.MIN_PORT)
        maxport = self.policy(policy.MAX_PORT)
        maxport = max(minport,maxport)
        minport = randrange(minport,maxport)
        args = ['--minport',minport,
                '--maxport',maxport,
                '--max_upload_rate',self.policy(policy.MAX_UPLOAD_RATE),
                '--max_download_rate',self.policy(policy.MAX_DOWNLOAD_RATE)]
        self.controller = LaunchManyThread(OutputHandler(self.cb_restart),args,self.cb_ban)
        self.queue = Scheduler(self.controller,self.cb_dispatch,self.cb_error)
        self.prompt = '>>> '
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
        return result

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
        print msg

    def cb_restart(self):
        try:
            self.controller.stop()
            self.queue.stop()
            self.webservice.stop()
            self.policy.save()

            del self.controller
            del self.queue
            del self.webservice
        except Exception,why:
            pass

        from random import randrange
        minport = self.policy(policy.MIN_PORT)
        maxport = self.policy(policy.MAX_PORT)
        maxport = max(minport,maxport)
        args = ['--minport',minport,
                '--maxport',maxport,
                '--max_upload_rate',self.policy(policy.MAX_UPLOAD_RATE),
                '--max_download_rate',self.policy(policy.MAX_DOWNLOAD_RATE)]

        self.controller = LaunchManyThread(OutputHandler(self.cb_restart),args)
        self.queue = Scheduler(self.controller,self.cb_dispatch,self.cb_error)

        self.controller.start()
        self.queue.start()
        self.webservice = WebServiceServer(WebServiceRequestHandler,
                                           self.queue)
        self.webservice.start()

    def cb_dispatch(self,item,cb_finished,cb_failed):
        item.cb_finished = cb_finished
        item.cb_failed = cb_failed
        self.controller.add(item)
        #th = BTDownloadThread(item,cb_finished,cb_failed)
        #item.thread = th
        #th.start()

#    def thread_dispatch(self,item,cb_finished):
#        print item
#        time.sleep(5)
#        cb_finished(item)

    def apply_debug_level(self,level):
        import httplib
        if level == 0:
            httplib.HTTPConnection.debuglevel = 0
        elif level >= 2:
            httplib.HTTPConnection.debuglevel = 1
        self.log.set_debug_level(level)

    def mainloop(self):
        self.controller.start()
        self.queue.start()
        self.webservice = WebServiceServer(WebServiceRequestHandler,
                                           self.queue)
        self.webservice.start()
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            pass
        except Exception,why:
            import traceback
            traceback.print_exc()
        self.do_quit()

    def emptyline(self):
        self.do_list(' '.join([STATE_RUNNING,STATE_SEEDING]))

    def do_version(self,line=None):
        print version

    def do_shell(self,line=None):
        os.system(line)

    def do_last_banned(self,line=None):
        '''show last banned ip'''
        try:
            n = int(line)
        except ValueError:
            n = self.max_last_banned
        for ip in self.last_banned[-n:]:
            try:
                cc,netname = self.ipdb[line].split(':')
            except:
                cc,netname = 'XX','Unknown'
            print '%-16s %-2s %s' % (ip,cc,netname)

    def do_add(self,line=None):
        '''add new torrent'''
        file = line
        if file.find('://') == -1:
            file = os.path.realpath(file)
        try:
            result = self.queue.add_url(file)
        except Exception,why:
            import traceback
            traceback.print_exc()
            print why
        if result:
            print result

    def do_remove(self,line=None):
        '''remove given torrent out of queue'''
        item = self.queue.job(line)
        if not item:
            print '%s not found' % item
            return
        self.queue.remove(item)

    def do_pause(self,line=None):
        '''put the specified torrent in pause state'''
        item = self.queue.job(line)
        if not item:
            print '%s not found' % item
            return
        self.queue.pause(item)

    def do_resume(self,line=None):
        '''resume paused torrent'''
        item = self.queue.job(line)
        if not item:
            print '%s not found' % item
            return
        self.queue.resume(item)

    def do_hold(self,line=None):
        '''temporarily stop downloading the specified torrent, states are still keeping in memory'''
        item = self.queue.job(line)
        if not item:
            print '%s not found' % item
            return
        self.queue.hold(item)

    def do_unhold(self,line=None):
        '''continue downloading the stopped torrent'''
        item = self.queue.job(line)
        if not item:
            print '%s not found' % item
            return
        self.queue.unhold(item)

    def do_gset(self,line=None):
        '''set global policy'''
        try:
            key,value = line.split(' ')
        except ValueError,why:
            print why
            return
        self.policy.update(key,value)
        self.policy.save()

    def do_gget(self,line=None):
        '''get global policy'''
        try:
            value = self.policy(line)
            if value == None:
                raise ValueError
            print '%-20s %s' % (line+':',str(value))
        except ValueError,why:
            gkeys = self.policy.keys()
            gkeys.sort()
            for key in gkeys:
                print '%-20s %s' % (str(key)+':',str(self.policy(key)))

    def do_lset(self,line=None):
        '''set local policy'''
        try:
            jid,key,value = line.split(' ')
        except ValueError,why:
            print why
            return
        j = self.queue.job(jid)
        if not j:
            print jid,'not found'
            return
        lpol = j.get_policy()
        lpol.update(key,value)

    def do_lget(self,line=None):
        '''get local policy'''
        args = line.split(' ')
        if len(args) < 1:
            print 'need id'
            return
        j = self.queue.job(args[0])
        if not j:
            print args[0],'not found'
            return
        lpol = j.get_policy()
        try:
            value = lpol(line)
            if value == None:
                raise ValueError
            print '%-20s %s' % (line+':',str(value))
        except ValueError,why:
            lkeys = lpol.keys()
            lkeys.sort()
            for key in lkeys:
                print '%-20s %s' % (str(key)+':',str(lpol(key)))

    def do_iset(self,line=None):
        '''set an item attribute'''
        args = line.split(' ',2)
        if len(args) < 3:
            print 'need an id, an attribute and a value'
            return
        id,attr,value = args
        j = self.queue.job(id)
        if not j:
            print id,'not found'
            return
        if not hasattr(j,attr):
            print 'attribute',attr,'not found'
            return
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
                print 'unable to change',str(atype)
                return
        except Exception,why:
            print 'value error:',why
            return
        resume = 0
        if j.state in [STATE_RUNNING,STATE_SEEDING]:
            self.queue.pause(j)
            resume = 1
        setattr(j,attr,value)
        if resume:
            self.queue.resume(j)
        self.queue.save()

    def do_iget(self,line=None):
        '''get item attributes'''
        args = line.split(' ',1)
        if len(args) < 1:
            print 'need an id and an optional attribute'
            return
        try:
            id,attr = args
            attrs = [attr]
        except ValueError:
            id,attrs = args[0],QueueEntry.modifiable_vars
        j = self.queue.job(id)
        if not j:
            print id,'not found'
            return
        for attr in attrs:
            if not hasattr(j,attr):
                print 'attribute',attr,'not found'
                return
            print '%-20s %s' % (attr+':',str(getattr(j,attr)))

    def do_list(self,line=None):
        '''list torrent queue'''
        if line:
            accept_state = line.split(' ')
        else:
            accept_state = [STATE_WAITING,STATE_RUNNING,STATE_FINISHED,STATE_SEEDING,STATE_PAUSED,STATE_HOLDED]
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
            data['title'] = quoted_title[:20]
            data['dlsize'] = data['dlsize'].split()[0]
            data['totalsize'] = data['totalsize'].split()[0]
            data['dlspeed'] = data['dlspeed'].split()[0]
            data['ulspeed'] = data['ulspeed'].split()[0]
            print '%(id)2s %(title)-20s %(progress)6s %(dlsize)7s/%(totalsize)-7s ' % data,
            print '%(eta)8s %(dlspeed)4s %(ulspeed)4s ' % data,
            print '%(seeds)6s %(peers)6s %(btstatus)10s %(ratio)6s' % data,
            print '%(activity)s' % vars(j)

    def do_bw(self,line=None):
        '''Show total upload / download rates'''
        dlspeed = 0
        ulspeed = 0
        for j in self.queue.jobs():
            data = j.get()
            dlspeed += float(data['dlspeed'].split()[0])
            ulspeed += float(data['ulspeed'].split()[0])
        max_dl = float(self.policy('max_download_rate'))
        max_ul = float(self.policy('max_upload_rate'))
        print 'Download Speed: %4s (%4s%%)' % (dlspeed, dlspeed*100/max_dl)
        print 'Upload Speed:   %4s (%4s%%)'% (ulspeed, ulspeed*100/max_ul)
            
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
        if not line:
            print 'need id'
            return
        j = self.queue.job(line)
        if not j:
            print line,'not found'
            return
        spew = j.get_spew()
        for i in spew:
            var = {}
            var.update(i)
            try:
                var['cc'],var['netname'] = self.ipdb[i['ip']].split(':')
            except (IndexError,TypeError,KeyError,AssertionError):
                var['cc'],var['netname'] = 'XX','Unknown'
            var['client'] = var['client'][:12]
            var['netname'] = var['netname'][:11]
            print '%(ip)-15s %(cc)2s %(direction)s %(uprate)4s %(downrate)4s %(dtotal)7s %(utotal)7s %(completed)7s %(client)-12s %(netname)s' % var

    def do_ip(self,line=None):
        '''display full information of given IP'''
        try:
            cc,netname = self.ipdb[line].split(':')
            fqdn = socket.getfqdn(line)
            if line == fqdn:
                fqdn = 'not registered'
        except:
            print '%s not in database' % line
            return
        print 'IP: %s\nFQDN: %s\nCountry: %s\nNetName: %s' % \
              (line,fqdn,cc,netname)

    def do_meta(self,line=None):
        '''display all metadata of given torrent id'''
        if not line:
            print 'need id or path or url'
            return
        j = self.queue.job(line)
        if j:
            meta = j.get_meta()
            detail = j.get()
            info = meta['info']
        else:
            try:
                from scheduler import urlopen as _urlopen
                from queue import sha,bdecode
                if line.find('://') == -1:
                    line = os.path.realpath(line)
                meta = bdecode(_urlopen(line).read())
                info = meta['info']
                detail = {'infohash':sha(bencode(info)).hexdigest()}
            except Exception,why:
                print line,why
                return

        print '%-20s %s' % ('infohash:',detail['infohash'])
        for key in meta.keys():
            if not key in ['info','name','length','files','resume']:
                print '%-20s %s' % (key+':',str(meta[key]))
        print '%-20s' % 'files:'
        if info.has_key('length'):
            print '%15ld %s' % (info['length'],info['name'])
        else:
            length = 0
            for i in info['files']:
                length += i['length']
                print '%15ld %s' % \
                      (i['length'],apply(os.path.join,[info['name']]+i['path']))
            print '%-20s %ld' % ('length:',length)

    def do_detail(self,line=None):
        '''display detail of given torrent id'''
        if not line:
            print 'need id'
            return
        j = self.queue.job(line)
        if not j:
            print line,'not found'
            return
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
''' % data

    def do_reannounce(self,line=None):
        '''reannounce now'''
        if not line:
            print 'need id'
            return
        j = self.queue.job(line)
        if not j:
            print line,'not found'
            return
        if j.dow:
            j.dow.reannounce()

    def do_superseed(self,line=None):
        '''turn on superseed mode'''
        if not line:
            print 'need id'
            return
        j = self.queue.job(line)
        if not j:
            print line,'not found'
            return
        if j.dow:
            j.dow.set_super_seed()

    def do_resched(self,line=None):
        '''schedule now'''
        self.queue.schedule()

    def do_savequeue(self,line=None):
        '''save queue immediately'''
        self.queue.save()

    def do_wget(self,line=None):
        '''retrieve http content using get'''
        if not line:
            print 'need url'
            return
        try:
            content = urlopen(line,method='get').read()
            print html2text(content).encode('iso-8859-1')
        except Exception,why:
            import traceback
            traceback.print_exc()
            print why

    def do_wpost(self,line=None):
        '''retrieve http content using post'''
        if not line:
            print 'need url'
            return
        try:
            content = urlopen(line,method='post').read()
            print html2text(content).encode('iso-8859-1')
        except Exception,why:
            print why

    def do_quit(self,line=None):
        '''quit'''
        self.queue.save()
        self.controller.stop()
        self.queue.stop()
        self.webservice.stop()
        self.policy.save()
        return 1

    do_exit = do_quit
    do_EOF = do_quit
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
        cmds = find_cmds(cmd)
        lcmds = len(cmds)
        if lcmds == 0:
            print '*** Unknown syntax: %s' % line
        elif lcmds > 1:
            print '*** Ambiguous command: %s' % ' '.join([c[3:] for c in cmds])
        else:
            apply(getattr(self,cmds[0]),(args,))
