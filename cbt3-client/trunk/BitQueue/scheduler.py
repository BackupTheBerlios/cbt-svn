#!/usr/bin/python

from threading import Thread,Lock,Event,Semaphore
from Queue import Queue as SyncQueue
from urllib2 import URLError,HTTPError,build_opener
from base64 import encodestring, decodestring
import urllib
import os,random
import time
from BitCrawler.aurllib import urlopen as aurlopen

from queue import Queue,QueueEntry,History
import policy
from i18n import *

try:
    from BitTornado.BT1.download import Download
    from BitTornado.BT1.bencode import bencode, bdecode
except ImportError,why:
    try:
        from BitTorrent.download import Download
        from BitTorrent.bencode import bencode, bdecode
    except ImportError:
        print 'BitTorrent not found'
        import sys
        sys.exit()

try:
    sum([1])
except NameError:
    def sum(seq,start=0):
        s = 0
        for i in seq[start:]:
            s += i
        return s

_opener = None
def urlopen(url,data=None):
    global _opener
    if not _opener:
        _opener = build_opener()
        _opener.addheaders = [('User-Agent',
                               'Mozilla/4.0 (compatible; Windows; Linux)')]

    #_urlopen = _opener.open
    _urlopen = aurlopen

    try:
        fd = _urlopen(url,data)
    except HTTPError,why:
        raise HTTPError,why
    except (ValueError,URLError,OSError),why:
        try:
            fd = _urlopen(urllib.unquote(url),data)
        except HTTPError,why:
            raise HTTPError,why
        except (ValueError,URLError,OSError),why:
            from nturl2path import pathname2url
            try:
                fd = _urlopen('file:'+pathname2url(url),data)
            except HTTPError,why:
                raise HTTPError,why
            except (ValueError,URLError,OSError):
                fd = _urlopen('file:'+pathname2url(urllib.unquote(url)))
    return fd

class Scheduler(Thread):

    file_semaphore = Semaphore()

    def __init__(self,controller,dispatch,error):
        Thread.__init__(self)
        self.policy = policy.get_policy()
        self.controller = controller
        self.do_dispatch = dispatch
        self.error = error
        self.queue = Queue()
        self.queue.load()
        self.lock = Lock()
        self._quit = Event()

        self.add_queue = SyncQueue(0)
        self.num_run = 0

    def job(self,id):
        return self.queue.get(id)

    def jobs(self):
        return self.queue.get()

    def save(self):
        self.queue.save()

    def add(self,item):
        if self.lock.acquire(0):
            self.queue.add(item)
            self.lock.release()
        else:
            self.add_queue.put(item)

    def add_url(self,url):
        try:
            fd = urlopen(url)
            meta = fd.read()
            fullurl = fd.geturl()
            fd.close()
            save_torrent = 1
            if fullurl.startswith('file://'):
                torrent_file = urllib.unquote(url)
                if torrent_file.startswith('file://'):
                    torrent_file = torrent_file[7:]
            elif fullurl.startswith('file:/') and fullurl[8] == '|':
                torrent_file = urllib.unquote(url)
                torrent_file = torrent_file[7]+':'+torrent_file[9:]
                if torrent_file.find('Temporary Internet Files') >= 0:
                    filename = os.path.split(url)[1]
                    torrent_file = os.path.join(self.policy(policy.TORRENT_PATH),
                                                filename)
            else:
                filename = urllib.unquote(os.path.split(url)[1])
                torrent_file = os.path.join(self.policy(policy.TORRENT_PATH),
                                            filename)

            torrent_path = os.path.dirname(torrent_file)
            if not os.path.exists(torrent_path):
                os.mkdir(torrent_path)

            if save_torrent:
                fd = open(torrent_file,'wb')
                fd.write(meta)
                fd.close()

            #~ d = Download() #cbt
            
            try: #cbt
                rd = bdecode(meta) #cbt
                if rd['cbt_user'] == self.policy(policy.CBT_LOGIN): #cbt
                    dest_path = rd['cbt_path'] #cbt
            except: #cbt
                    dest_path = self.policy(policy.DEST_PATH) #cbt

            self.add(QueueEntry(torrent_file, dest_path=dest_path)) #cbt

        except Exception,why:
            return str(why)

    def remove(self,item):
        self.pause(item)
        self.lock.acquire()
        self.queue.remove(item)
        self.lock.release()

    def pause(self,item):
        if item.state == STATE_PAUSED:
            return
        if item.state in [STATE_RUNNING,STATE_SEEDING]:
            self.controller.remove(item)
            self.num_run -= 1
        item.old_state = item.state
        if item.state == STATE_SEEDING:
            item.state = STATE_FINISHED
        else:
            item.state = STATE_PAUSED
        item.paused()

    def resume(self,item):
        if item.state == STATE_HOLDED:
            self.unhold(item)
            return
        if item.state in [STATE_RUNNING,STATE_SEEDING]:
            item.done_flag.set()
        item.state = STATE_WAITING
        self.schedule()

    def hold(self,item):
        if item.state == STATE_HOLDED:
            return
        if item.state in [STATE_RUNNING,STATE_SEEDING]:
            item.dow.Pause()
            self.num_run -= 1
        item.old_state = item.state
        item.state = STATE_HOLDED
        item.clear_stat()

    def unhold(self,item):
        if item.state == STATE_HOLDED:
            item.dow.Unpause()
            self.num_run += 1
        item.state = item.old_state

    def dispatch(self,item):
        item.state = STATE_RUNNING
        minport = self.policy(policy.MIN_PORT)
        maxport = self.policy(policy.MAX_PORT)
        minpeer = self.policy(policy.MIN_PEER)
        maxpeer = self.policy(policy.MAX_PEER)
        maxport = max(minport,maxport)
        rerequest_interval = self.policy(policy.REREQUEST_INTERVAL)
        minport = random.randrange(minport,maxport)
        item.params = ['--minport',minport,
                       '--maxport',maxport,
                       '--min_peers',minpeer,
                       '--max_initiate',maxpeer,
                       '--spew',1,
                       '--rerequest_interval',rerequest_interval,
                       '--saveas',item.dest_path,
                       '--max_upload_rate',self.policy(policy.MAX_UPLOAD_RATE),
                       '--max_download_rate',self.policy(policy.MAX_DOWNLOAD_RATE)]
        report_ip = self.policy(policy.REPORT_IP)
        if report_ip:
            item.params += ['--ip',report_ip]
        item.params += [item.file]
        self.num_run += 1
        self.do_dispatch(item,self.cb_finished,self.cb_failed)

    def cb_finished(self,item):
        self.lock.acquire()
        item.state = STATE_FINISHED
        self.lock.release()

        hist = History()
        hist.load()
        hist.add(item.file)
        hist.save()

        self.schedule()

    def cb_failed(self,item):
        #item.state = STATE_WAITING
        pass

    def calculate_upload_rate(self):
        completes = []
        incompletes = []
        used_bw = 0
        new_up_rates=[]
        for j in self.queue.get():
            # duplicate with download rate
            #j.update_scrape()
            if not j.dow or not hasattr(j.dow,'downloader'):
                continue
            if j.state == STATE_RUNNING:
                incompletes.append(j)
                new_up_rates.append(j.up_rate/1000)
            if j.state == STATE_SEEDING:
                completes.append(j)
                new_up_rates.append(j.up_rate/1000)
        used_bw = sum(new_up_rates)
        all = incompletes+completes
        max_bw = float(self.policy(policy.MAX_UPLOAD_RATE))
        max_seed_rate = float(self.policy(policy.MAX_SEED_RATE))
        avail_bw = max_bw - used_bw
        active_ups = len(all)
        new_up_rates = []
        if used_bw == 0:
            return
        if avail_bw >= max_bw * 0.85 and active_ups > 1 and len(new_up_rates) == active_ups:
            avail_avg_bw = avail_bw / active_ups
            while avail_bw > 0.5:
                for uj in range(active_ups):
                    new_rate = new_up_rates[uj] + avail_avg_bw
                    if all[uj].state == STATE_RUNNING and new_rate < 0.9 * max_bw:
                        new_up_rates[uj] = new_rate
                        avail_bw += -new_rate
                    elif all[uj].state == STATE_SEEDING and new_rate < 0.9 * max_seed_rate:
                        new_up_rates[uj] = new_rate
                        avail_bw += -new_rate
                    else:
                        pass
                    avail_avg_bw = avail_bw / active_ups
        else:
            for j in all:
                if j.state == STATE_RUNNING:
                    new_up_rates.append(max_bw)
                else:
                    new_up_rates.append(max_seed_rate)       
        for j in map(None,all,new_up_rates):
            j[0].dow.setUploadRate(j[1])

    def calculate_download_rate(self):
        '''Simple download rate adjuster.  Could be enhanced with priorities.'''
        completes = []
        incompletes = []
        used_bw = 0
        dl_rates = []
        for j in self.queue.get():
            # duplicate with upload rate
            #j.update_scrape()
            if not j.dow or not hasattr(j.dow,'downloader'):
                continue
            if j.state == STATE_RUNNING:
                incompletes.append(j)
                dr = j.down_rate/1000
                dl_rates.append(dr)
        max_bw = min(float(self.policy(policy.MAX_DOWNLOAD_RATE)),1000000)
        active_downs=len(incompletes)
        average_max_bw = max_bw / active_downs
        used_bw = sum( dl_rates )
        if used_bw == 0:
            return
        if len(incompletes) > 1 and used_bw >= max_bw * 0.85:
            avail_bw = max_bw - used_bw
            avail_avg_bw = avail_bw / active_downs
            soft_max_perc_allowed = 0.9
            while avail_bw > 0.5:
                for act in range(active_downs):
                    new_rate=dl_rates[act] + avail_avg_bw
                    if new_rate < (soft_max_perc_allowed + (1 - soft_max_perc_allowed) / active_downs) * max_bw:
                        dl_rates[act] = new_rate
                        avail_bw += -avail_avg_bw
                avail_avg_bw = avail_avg_bw / active_downs
        else:
            dl_rates = [max_bw] * len(incompletes)
        for j in map(None,incompletes,dl_rates):
                j[0].dow.setDownloadRate(j[1])
    
    def terminate_seeding(self):
        for j in self.queue.get():
            pol = j.get_policy()
            if pol(policy.USE_LOCAL_POLICY):
                min_share_ratio = pol(policy.MIN_SHARE_RATIO)
            else:
                min_share_ratio = self.policy(policy.MIN_SHARE_RATIO)
            if j.state == STATE_SEEDING and j.share_ratio > min_share_ratio:
                self.pause(j)

    def schedule(self):
        self.lock.acquire()
        while 1:
            item = self.queue.get_next()
            if not item:
                break
            if self.num_run >= self.policy(policy.MAX_JOB_RUN):
                break
            self.dispatch(item)
        # we are using global upload rate
        # modify launchmanycore before enable this feature
        try:
            if 0:
                self.calculate_upload_rate()
            self.calculate_download_rate()
        except Exception,why:
            pass
        for j in self.queue.get():
            j.update_scrape()
        self.terminate_seeding()
        self.queue.save()
        self.lock.release()

        while not self.add_queue.empty():
            self.add(self.add_queue.get())

    def stop(self):
        self._quit.set()
        for j in self.queue.get():
            self.controller.remove(j)
            #if hasattr(j,'thread'):
            #    j.thread.stop()
            #    if j.thread.isAlive():
            #        print 'waiting %s' % j.id
            #        j.thread.join()
            #        print 'terminated %s' % j.id
            if hasattr(j,'scrape_thread'):
                if j.scrape_thread.isAlive():
                    print 'waiting scrape %s' % j.id
                    j.scrape_thread.join()
                    print 'terminated scrape %s' % j.id
        self.queue.save()

    def run(self):
        while not self._quit.isSet():
            self.schedule()
            self._quit.wait(self.policy(policy.SCHEDULING_INTERVAL))
        print 'queue stopped'

class BTDownloadThread(Thread):
    def __init__(self,item,cb_finished,cb_failed):
        Thread.__init__(self)
        self.item = item
        self.cb_finished = cb_finished
        self.cb_failed = cb_failed

    def run(self):
#        print self.item
#        time.sleep(5)
#        self.finished()
        print 'download started %s' % self.item.id
        dow = Download()
        self.item.dow = dow
        dow.download(self.item.params,
                     self.choose_file,
                     self.update_status,
                     self.finished,
                     self.error,
                     self.item.done_flag,
                     100,
                     self.new_path,
                     sem=Scheduler.file_semaphore,
                     old_dlsize=self.item.old_dlsize,
                     old_ulsize=self.item.old_ulsize)
        self.item.done_flag.clear()
        if self.item.state in [STATE_FINISHED,STATE_SEEDING]:
            self.cb_failed(self.item)
        print 'download stopped %s' % self.item.id

    def stop(self):
        self.item.done_flag.set()

    def error(self,msg):
        self.item.error = time.strftime('%H:%M - ')+msg

    def new_path(self,path):
        self.item.dest_path = path

    def choose_file(self,default,size,saveas,dir):
        return saveas or default

    def update_status(self,fractionDone=None,
                      timeEst=None,downRate=None,upRate=None,
                      activity=None,statistics=None,spew=None,sizeDone=None,
                      **kws):
        apply(self.item.update_info,(fractionDone,timeEst,downRate,upRate,
                                activity,statistics,spew,sizeDone),kws)
 
    def finished(self):
        self.cb_finished(self.item)
        self.item.state = STATE_SEEDING
        self.item.activity = None
        self.item.clear_stat()
