#!/usr/bin/python

from ConfigParser import ConfigParser,NoOptionError
from threading import Thread,Event
from binascii import a2b_hex
from sha import sha
from log import get_logger
import urllib,os
import time

try:
    from BitTornado.bencode import bdecode,bencode
except ImportError:
    try:
        from BitTorrent.bencode import bdecode,bencode
    except ImportError:
        print 'BitTorrent not found'
        import sys
        sys.exit()

from __init__ import mapbase64,decode_build,cmp_version
from scrape import getScrapeData
import policy
from i18n import *

def hours(n):
    if n == -1:
        return '--:--:--'
    if n == 0:
        return ''
    n = long(n)
    h, r = divmod(n, 60 * 60)
    m, sec = divmod(r, 60)
    if h > 1000000:
        return '--:--:--'
    ret = '%d:%02d:%02d' % (h, m, sec)
    if len(ret) > 8:
        ret = '--'+ret[-6:]
    return ret

class IDGenerator:
    def __init__(self,start=0):
        self.id = start

    def reset(self,id=0):
        self.id = id

    def generate(self):
        self.id += 1
        return str(self.id)

id_generator = IDGenerator()

def decode_peer_id(id):
    try:
        client = _decode_peer_id(id)
    except:
        client = 'N/A'
    return client

def _decode_peer_id(id):
    quoted_id = id

    if id[:3] == '0x ':
        id = a2b_hex(id[3:])
    if id[0] == '"' and id[-1] == '"':
        id = id[1:-1]
    if len(id) == 40:
        id = a2b_hex(id)

    if id[0] == 'S':
        if id[6:6+3] == '---':
            ver = list(id[1:1+3])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'S '+'.'.join(ver)
            return name
        if ord(id[8]) == 0:
            ver = list(id[1:1+3])
            for i in range(3):
                ver[i] = str(ord(ver[i]))
            name = 'S '+'.'.join(ver)
            return name
        if id[4:4+7] == 'Plus---':
            ver = list(id[1:1+3])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'S '+'.'.join(ver)+' Plus'
            return name

    if id[0] == 'T':
        if id[6:6+3] == '---':
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'BT '+'.'.join(ver)
            return name
        if id[6] in mapbase64 and id[7] in mapbase64 and id[8] in mapbase64:
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'BT '+'.'.join(ver)+' M'
            return name

    if id[0] == 'A':
        if id[6:6+3] == '---':
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'ABC '+'.'.join(ver)
            return name
        if id[6] in mapbase64 and id[7] in mapbase64 and id[8] in mapbase64:
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            name = 'ABC '+'.'.join(ver)+' M'
            return name

    if id[0] == 'Q':
        if id[6:6+3] == '---' or \
           (id[6] in mapbase64 and id[7] in mapbase64 and id[8] in mapbase64):
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            ver_str = '.'.join(ver)
            name = 'BTQ '+ver_str
            if cmp_version(ver_str,'0.0.7') >= 0:
                build = decode_build(id[9:9+3])
                if build:
                    name += ' '+str(build)
            return name
        elif id[1] in mapbase64[:16] and \
             id[2] in mapbase64[:16] and \
             id[3] in mapbase64[:16]:
            ver = list(id[1:4])
            for i in range(3):
                ver[i] = str(int(ver[i],16))
            ver_str = '.'.join(ver)
            name = 'BTQ '+ver_str
            return name

    if id[1:1+2] == 'AZ':
        name = 'Az '+'.'.join(list(id[3:3+4]))
        return name

    if id[5:5+7] == 'Azureus':
        name = 'Az 2.0.3.2'
        return name

    if id[2:2+2] == 'BS':
        if ord(id[1]) == 0:
            name = 'BS v1'
        if ord(id[1]) == 2:
            name = 'BS v2'
        return name

    if id[0] == 'U':
        if id[8] == '-':
            name = 'UPnP '+'.'.join(list(id[1:1+3]))
            return name

    if id[0] == 'M' and id[2] == '-' and id[4] == '-' and id[6:6+2] == '--':
        name = 'ML %s.%s.%s' % (id[1],id[3],id[5])
        return name

    if id[:4] == 'exbc':
        name = 'BC '
        name += '%c.%c%c' % (str(ord(id[4])),str(ord(id[5])/10),str(ord(id[5])%10))
        return name

    if id[:7] == 'turbobt':
        name = 'TBT '+id[7:7+5]
        return name

    if id[:12] == '-G3g3rmz    ':
        name = 'G3'
        return name

    if id[:3] == '-G3':
        name = 'G3'
        return name

    if id[:7] == 'Plus---' or (id[:4] == 'Plus' and id[7] == '-'):
        name = 'BT Plus'
        return name

    if id[:16] == 'Deadman Walking-' or id[:6] == 'BTDWV-':
        name = 'Deadman'
        return name

    if id[1:1+2] == 'LT':
        name = 'libt '+'.'.join(list(id[3:3+4]))
        return name

    if id[1:1+2] == 'TS':
        name = 'TS '+'.'.join(list(id[3:3+4]))
        return name

    if id[1:1+2] == 'MT':
        name = 'MT '+'.'.join(list(id[3:3+4]))
        return name

    if id[:12] == '\000\000\000\000\000\000\000\000\000\003\003\003':
        name = 'Snark'
        return name

    if id[:5] == 'btuga':
        name = 'BTugaXP'
        return name

    if id[4:4+6] == 'btfans':
        name = 'SBT'
        return name

    if id[:10] == 'DansClient':
        name = 'XT'
        return name

    if id[:14] == '\000\000\000\000\000\000\000\000\000\000\000\000aa':
        name = 'Exp 3.2.1b2'
        return name

    if id[:14] == '\000\000\000\000\000\000\000\000\000\000\000\000\000\000':
        name = 'Exp 3.1'
        return name

    if id[:12] == '\000\000\000\000\000\000\000\000\000\000\000\000':
        name = 'Generic'
        return name

    if id[:2] == '[]':
        return 'N/A'

    pol = policy.get_policy()
    if pol(policy.LOG_UNKNOWN_ID):
        unknown_log = pol.get_path(policy.UNKNOWN_ID_FILE)
        try:
            fd = open(unknown_log,'a')
            fd.write(id+' '+quoted_id+'\n')
            fd.close()
        except Exception,why:
            pass

    return quoted_id

class QueueEntry:

    all_fields = ['filename','progress','btstatus','eta',
                  'dlspeed','ulspeed',
                  'ratio','peers','seeds','copies','dlsize','ulsize',
                  'peeravgprogress','totalspeed','totalsize',
                  'error','id','infohash','title','activity','announce',
                  'dest_path','peer_id',
                  'added_time','started_time','finished_time','stopped_time']
    default_fields = ['filename','progress','btstatus','eta',
                      'dlspeed','ulspeed',
                      'ratio','peers','seeds','copies','dlsize','ulsize',
                      'peeravgprogress','totalspeed','totalsize','title',
                      'added_time','started_time','finished_time','stopped_time']
    header_fields = {'filename': 'Filename',
                     'progress': 'Progress',
                     'btstatus': 'BT Status',
                     'eta': 'ETA',
                     'dlspeed': 'DL Speed',
                     'ulspeed': 'UL Speed',
                     'ratio': '%UL/DL',
                     'peers': '#Peers',
                     'seeds': '#Seeds',
                     'copies': '#Copies',
                     'dlsize': 'DL Size',
                     'ulsize': 'UL Size',
                     'peeravgprogress': 'Peer Avg Progress',
                     'totalspeed': 'Total Speed',
                     'totalsize': 'Total Size',
                     'error': 'Error',
                     'id': 'ID',
                     'peer_id': 'Peer ID',
                     'announce': 'Announce',
                     'infohash': 'Info Hash',
                     'title': 'Title',
                     'dest_path': 'Destination',
                     'activity': 'Activity',
                     'added_time': 'Added',
                     'started_time': 'Started',
                     'finished_time': 'Finished',
                     'stopped_time': 'Stopped'}
    modifiable_vars = ['title','dest_path','file','priority',
                       'dlsize','ulsize',
                       'old_dlsize','old_ulsize','recheck']

    def __init__(self,file,priority=-1,dest_path='',id_generator=id_generator):
        if id_generator:
            self.id = id_generator.generate()
        else:
            self.id = 0
        self.file = file
        self.global_policy = policy.get_policy()
        if priority >= 0:
            self.priority = priority
        else:
            self.priority = self.global_policy(policy.DEFAULT_PRIORITY)
        self.local_policy = policy.EntryPolicy()
        self.state = STATE_WAITING
        self.done_flag = Event()
        self.dest_path = dest_path
        self.dlsize = self.ulsize = self.old_dlsize = self.old_ulsize = 0
        self.error = ''
        self.gather_info()
        self.statistics = None
        self.spew = None
        self.dow = self.listen_port = None
        self.share_ratio = 0.0
        self.currentseed = '?'
        self.currentpeer = '?'
        self.recheck = 0

        self.added_time = -1
        self.started_time = -1
        self.finished_time = -1
        self.stopped_time = -1
        self.added()

        self.update_info(fractionDone=0.0,
                         timeEst=0.0,downRate=0.0,upRate=0.0,
                         activity='None',statistics=None,
                         spew=None,sizeDone=0,force=True)

    def get_spew(self):
        if not self.spew:
            return []
        spew = []
        for i in self.spew:
            d = {}
            d['ip'] = i['ip']
            d['direction'] = i['direction']
            d['uprate'] = '%.1f' % (i['uprate']/1000.0)
            d['downrate'] = '%.1f' % (i['downrate']/1000.0)
            if i['dtotal'] is not None:
                d['dtotal'] = '%.2f' % (float(i['dtotal'])/(1 << 20))
            else:
                d['dtotal'] = '%.2f' % 0
            if i['utotal'] is not None:
                d['utotal'] = '%.2f' % (float(i['utotal'])/(1 << 20))
            else:
                d['utotal'] = '%.2f' % 0
            d['completed'] = '%.1f%%' % (float(i['completed'])*1000.0/10)
            if i['speed'] is not None:
                d['speed'] = '%.1f' % (i['speed']/1000.0)
            else:
                d['speed'] = '%.1f' % 0
            d['id'] = i['id']
            d['client'] = decode_peer_id(i['id'])
            spew.append(d)
        return spew

    def get(self,key=None):
        if key == 'filename':
            return self.file
        elif key == 'progress':
            return '%.1f%%' % (self.fraction_done*100.0,)
        elif key == 'btstatus':
            return self.state
        elif key == 'eta':
            return hours(self.time_est)
        elif key == 'dlspeed':
            return '%.1f %s' % (self.down_rate/1000.0,UNIT_kBps)
        elif key == 'ulspeed':
            return '%.1f %s' % (self.up_rate/1000.0,UNIT_kBps)
        elif key == 'ratio':
            #if not self.statistics:
            #    return '0.0%'
            if self.dlsize == 0:
                return '---.-%'
            return '%.1f%%' % (self.ulsize*100.0/self.dlsize,)
        elif key == 'peers':
            if not self.statistics:
                return '0(%s)' % self.currentpeer
            return '%d(%s)' % (self.statistics.numPeers,self.currentpeer)
        elif key == 'seeds':
            if not self.statistics:
                return '0(%s)' % self.currentseed
            return '%d(%s)' % (self.statistics.numSeeds,self.currentseed)
        elif key == 'copies':
            if not self.statistics:
                return 0
            return self.statistics.numCopies
        elif key == 'dlsize':
            #if not self.statistics:
            #    return '0.00 %s' % UNIT_MB
            return '%.2f %s' % (self.dlsize/float(1 << 20),UNIT_MB)
        elif key == 'ulsize':
            #if not self.statistics:
            #    return '0.00 %s' % UNIT_MB
            return '%.2f %s' % (self.ulsize/float(1 << 20),UNIT_MB)
        elif key == 'peeravgprogress':
            if not self.statistics:
                return '0.0%'
            return '%.1f%%' % self.statistics.percentDone
        elif key == 'totalspeed':
            if not self.statistics:
                return '0 %s' % UNIT_kBps
            return '%.0f %s' % (self.statistics.torrentRate/1000.0,UNIT_kBps)
        elif key == 'totalsize':
            #if not self.statistics:
            #    return '%.2f %s' % (self.size/float(1 << 20),UNIT_MB)
            return '%.2f %s' % (self.size/float(1 << 20),UNIT_MB)
        elif key == 'activity':
            return self.infohash
        elif key == 'infohash':
            return self.infohash
        elif key == 'title':
            return self.title
        elif key == 'dest_path':
            return self.dest_path
        elif key == 'id':
            return self.id
        elif key == 'error':
            return self.error
        elif key == 'announce':
            return self.announce
        elif key == 'peer_id':
            try:
                peer_id = getattr(self.dow.d,'myid','-'*20)
            except:
                peer_id = '-'*20
            return peer_id
        elif key == 'added_time':
            return self.added_time
        elif key == 'started_time':
            return self.started_time
        elif key == 'finished_time':
            return self.finished_time
        elif key == 'stopped_time':
            return self.stopped_time
        elif key == None:
            dict = {}
            for key in self.all_fields:
                dict[key] = self.get(key)
            return dict
        else:
            return None

    def gather_info(self):
        self.fin = 0
        resp = self.get_meta()
        info = resp['info']
        self.announce = resp['announce']
        infohash_sha = sha(bencode(info))
        self.infohash_bin = infohash_sha.digest()
        self.infohash = infohash_sha.hexdigest()
        self.title = info['name']
        if info.has_key('length'):
            self.size = info['length']
            title = self.title.upper()
            if (title.startswith('AVSEQ') or \
                title.startswith('MUSIC')) and \
               title.endswith('.DAT') and \
               len(title) == 11:
                self.dest_path = os.path.join(self.dest_path,
                                              self.infohash+'-'+self.title)
            else:
                self.dest_path = os.path.join(self.dest_path,self.title)
        else:
            self.size = 0
            for i in info['files']:
                self.size += i['length']
        self.piece_length = info['piece length']
        self.size_mb = self.size/1024/1024

    def get_meta(self):
        fd = open(self.file,'rb')
        meta = bdecode(fd.read())
        fd.close()
        if meta.has_key('announce-list'):
            announce = meta['announce']
            found = 0
            for tier in meta['announce-list']:
                for tracker in tier:
                    if tracker == announce:
                        found = 1
            if not found:
                meta['announce-list'].append([announce])
        return meta

    def update_scrape(self):
        if hasattr(self,'scrape_thread') and self.scrape_thread.isAlive():
            return
        try:
            meta = self.get_meta()
            self.scrape_thread = Thread(target=getScrapeData,args=(meta,self))
            self.scrape_thread.start()
        except ValueError:
            pass

    def update_info(self,fractionDone=None,
                      timeEst=None,downRate=None,upRate=None,
                      activity=None,statistics=None,spew=None,sizeDone=None,
                      force=False,
                      **kws):
        if not force and not self.state in [STATE_RUNNING,STATE_SEEDING]:
            return
        if fractionDone != None:
            self.fraction_done = fractionDone
        if timeEst != None:
            self.time_est = timeEst
        if downRate != None:
            self.down_rate = downRate
        if upRate != None:
            self.up_rate = upRate
        if activity != None:
            self.activity = activity
        if statistics != None:
            self.statistics = statistics
            self.dlsize = self.statistics.downTotal
            self.ulsize = self.statistics.upTotal
            #down = self.old_dlsize+self.statistics.downTotal
            #up = self.old_ulsize+self.statistics.upTotal
            try:
                self.share_ratio = float(self.ulsize)/float(self.dlsize)
            except ZeroDivisionError:
                self.share_ratio = 0.0
        if spew != None:
            self.spew = spew
        if sizeDone != None:
            self.size_done = sizeDone
            if self.size_done > self.old_dlsize+self.dlsize:
                self.old_dlsize = self.size_done-self.dlsize
        #if self.statistics:
        #    if self.old_dlsize+self.dlsize > \
        #       self.statistics.downmeasure.get_total():
        #        self.statistics.downmeasure.total = self.old_dlsize+self.dlsize
        #    if self.old_ulsize+self.ulsize > \
        #       self.statistics.upmeasure.get_total():
        #        self.statistics.upmeasure.total = self.old_ulsize+self.ulsize

    def clear_stat(self):
        self.down_rate = self.up_rate = 0
        self.error = ''
        self.activity = 'None'
        self.time_est = 0
        self.currentpeer = self.currentseed = '?'
        self.spew = None
        self.statistics = None

    def get_policy(self):
        return self.local_policy or self.global_policy

    def paused(self):
        self.old_ulsize = self.ulsize
        self.old_dlsize = self.dlsize
        self.clear_stat()
        self.stopped()

    def __repr__(self):
        return '<%s,%s>' % (self.id,self.file)

    def __hash__(self):
        return self.id

    def __cmp__(self,other):
        try:
            return cmp(int(self.id),int(other.id))
        except ValueError:
            return cmp(self.id,other.id)

    def load(self,cfg,section=None):
        section = section or self.infohash
        try:
            self.id = cfg.get(section,'id')
            self.priority = cfg.getint(section,'priority')
            self.dest_path = cfg.get(section,'dest_path')
            self.old_dlsize = long(cfg.get(section,'old_dlsize'))
            self.old_ulsize = long(cfg.get(section,'old_ulsize'))
            self.added_time = float(cfg.get(section,'added_time'))
            self.started_time = float(cfg.get(section,'started_time'))
            self.finished_time = float(cfg.get(section,'finished_time'))
            self.stopped_time = float(cfg.get(section,'stopped_time'))
            self.local_policy = policy.EntryPolicy(cfg,section)
        except NoOptionError:
            pass

    def save(self,cfg,section=None):
        section = section or self.infohash
        cfg.add_section(section)
        cfg.set(section,'torrent',self.file)
        cfg.set(section,'id',self.id)
        cfg.set(section,'priority',str(self.priority))
        cfg.set(section,'dest_path',self.dest_path)
        cfg.set(section,'old_dlsize',str(max(self.old_dlsize,self.dlsize)))
        cfg.set(section,'old_ulsize',str(max(self.old_ulsize,self.ulsize)))
        cfg.set(section,'added_time',str(self.added_time))
        cfg.set(section,'started_time',str(self.started_time))
        cfg.set(section,'finished_time',str(self.finished_time))
        cfg.set(section,'stopped_time',str(self.stopped_time))
        self.local_policy.save(cfg,section)

    def added(self):
        self.added_time = time.time()

    def started(self):
        if self.started_time < 0:
            self.started_time = time.time()

    def finished(self):
        if self.finished_time < 0:
            self.finished_time = time.time()

    def stopped(self):
        self.stopped_time = time.time()

class Queue:
    def __init__(self):
        self.q = []
        self.queue_file = policy.get_policy().get_path(policy.QUEUE_FILE)
        #self.queue_file = os.path.join(root_path,QUEUE_FILE)
        self.log = get_logger()

    def load(self,file=None):
        reassign_id = policy.get_policy().get(policy.REASSIGN_ID)

        file = file or self.queue_file
        cfg = ConfigParser()
        cfg.read(file)
        self.log.debug('read %s\n' % file)

        sections = cfg.sections()
        if reassign_id:
            def _cmp(sa,sb):
                ia,ib = int(cfg.get(sa,'id')),int(cfg.get(sb,'id'))
                return cmp(ia,ib)
            sections.sort(_cmp)

        for section in sections:
            self.log.debug('added %s\n' % section)
            try:
                j = QueueEntry(cfg.get(section,'torrent'),id_generator=None)
                j.load(cfg)
                if reassign_id:
                    j.id = id_generator.generate()
                self.add(j,save=False)
            except NoOptionError:
                pass
            except IOError:
                pass
        self.q.sort()
#        for line in fd.readlines():
#            try:
#                j = QueueEntry(line.strip())
#                self.add(j)
#            except IOError:
#                pass

    def save(self,file=None):
        file = file or self.queue_file
        cfg = ConfigParser()
        for j in self.q:
            j.save(cfg)
#        for j in self.q:
#            fd.write(j.file+'\n')
        try:
            fd = open(file,'w')
            cfg.write(fd)
            fd.close()
        except Exception,why:
            return

    def size(self):
        return len(self.q)

    def add(self,item,save=True):
        while self.get_from_id(item.id):
            item.id = id_generator.generate()
        if self.get_from_infohash(item.infohash):
            return
        self.q.append(item)
        if save:
            self.save()

    def remove(self,item):
        self.q.remove(item)
        self.save()

    def get(self,key=None):
        if key == None:
            return self.q
        elif type(key) == type(0):
            return self.get_from_index(key)
        elif len(key) == 40:
            return self.get_from_infohash(key)
        else:
            return self.get_from_id(key)

    def get_next(self):
        q = self.q
        def priority_cmp(a,b):
            return cmp(a.priority,a.priority)
        q.sort(priority_cmp)
        for j in q:
            if j.state == STATE_WAITING:
                return j
        return None

    def get_from_infohash(self,infohash):
        for j in self.q:
            if j.infohash == infohash:
                return j
        return None

    def get_from_index(self,index):
        return self.q[index]

    def get_from_id(self,id):
        for j in self.q:
            if j.id == id:
                return j
        return None

class History:
    def __init__(self):
        self.history_file = policy.get_policy().get_path(policy.HISTORY_FILE)
        #self.history_file = os.path.join(root_path,HISTORY_FILE)
        self.new_history = []
        self.history = []

    def load(self):
        self.history = []
        try:
            fd = open(self.history_file,'r')
            for line in fd.readlines():
                line = line.strip()
                if line and not line in self.history:
                    self.history.append(line)
            fd.close()
        except Exception,why:
            pass

    def add(self,item):
        if not self.exists(item):
            self.history.append(item)
            self.new_history.append(item)

    def exists(self,item):
        return item in self.history or item in self.new_history

    def save(self):
        try:
            fd = open(self.history_file,'a+')
            for item in self.new_history:
                fd.write(item+'\n')
            fd.close()
        except Exception,why:
            pass
