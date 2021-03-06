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
from log import get_logger
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
def urlopen(url,data=None,referer=None):
    global _opener
    if not _opener:
        _opener = build_opener()
        _opener.addheaders = [('User-Agent',
                               'Mozilla/4.0 (compatible; Windows; Linux)')]

    #_urlopen = _opener.open
    _urlopen = aurlopen

    try:
        fd = _urlopen(url,data,referer=referer)
    except HTTPError,why:
        raise HTTPError,why
    except (ValueError,URLError,OSError),why:
        try:
            fd = _urlopen(urllib.unquote(url),data,referer=referer)
        except HTTPError,why:
            raise HTTPError,why
        except (ValueError,URLError,OSError),why:
            from nturl2path import pathname2url
            try:
                fd = _urlopen('file:'+pathname2url(url),data,referer=referer)
            except HTTPError,why:
                raise HTTPError,why
            except (ValueError,URLError,OSError):
                fd = _urlopen('file:'+pathname2url(urllib.unquote(url)),referer=referer)
    return fd

class RateController:

    MINIMUM_RATE = 3

    def __init__(self,job,current_rate):
        self.job = job
        self.current_rate = current_rate
        self.new_rate = current_rate

    def __repr__(self):
        return '(%s,%0.1f,%0.1f)' % (self.job.id,self.current_rate,self.new_rate)

    def apply(self):
        pass

    def __cmp__(self,o):
        return cmp(self.current_rate,o.current_rate)

    def change_rate(self,offset):
        self.new_rate = max(self.new_rate+offset,RateController.MINIMUM_RATE)

    def is_active(self):
        return self.current_rate > RateController.MINIMUM_RATE

    def is_seeding(self):
        return self.job.state == STATE_SEEDING

    def is_leeching(self):
        return self.job.state == STATE_RUNNING

class UploadRateController(RateController):
    def __init__(self,job):
        RateController.__init__(self,job,job.up_rate/1000.0)

    def apply(self):
        self.job.dow.setUploadRate(self.new_rate)

class DownloadRateController(RateController):
    def __init__(self,job):
        RateController.__init__(self,job,job.down_rate/1000.0)

    def apply(self):
        self.job.dow.setDownloadRate(self.new_rate)

def distribute_rate(jobs,avail_bw,threshold_bw,step):
    while avail_bw > 0:
        saved_bw = avail_bw
        for j in jobs:
            if j.is_active() and j.new_rate > threshold_bw:
                j.change_rate(-step)
                avail_bw -= step
            elif not j.is_active():
                j.change_rate(+avail_bw)
        if saved_bw == avail_bw:
            threshold_bw -= step

def change_rates(jobs,rate):
    for j in jobs:
        j.change_rate(rate)

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
        self.log = get_logger()

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

    def add_url(self,url,referer=None):
        try:
            fd = urlopen(url,referer=referer)
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
        item.started()
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
        item.finished()
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

        class RateController:
            def __init__(self,job):
                self.job = job
                self.current_up_rate = job.up_rate/1000.0
                self.new_up_rate = job.up_rate/1000.0

            def __repr__(self):
                return '(%s,%0.1f,%0.1f)' % (self.job.id,self.current_up_rate,self.new_up_rate)

            def apply(self):
                self.job.dow.setUploadRate(self.new_up_rate)

            def __cmp__(self,o):
                return cmp(self.current_up_rate,o.current_up_rate)

            def change_up_rate(self,offset):
                self.new_up_rate = max(self.new_up_rate+offset,3)

            def is_active(self):
                return self.current_up_rate > 3

            def is_seeding(self):
                return self.job.state == STATE_SEEDING

            def is_leeching(self):
                return self.job.state == STATE_RUNNING

        for j in self.queue.get():
            # duplicate with download rate
            #j.update_scrape()
            if not j.dow or not hasattr(j.dow.d,'downloader'):
                continue
            if j.state == STATE_RUNNING:
                incompletes.append(UploadRateController(j))
            if j.state == STATE_SEEDING:
                completes.append(UploadRateController(j))
        used_upload_bw = sum([j.current_rate for j in incompletes])
        used_seed_bw = sum([j.current_rate for j in completes])
        used_bw = used_upload_bw+used_seed_bw

        all = incompletes+completes

        max_bw = float(self.policy(policy.MAX_UPLOAD_RATE))
        max_seed_bw = float(self.policy(policy.MAX_SEED_RATE))
        max_upload_bw = max_bw-min(max_seed_bw,used_seed_bw)
        max_seed_bw = max(max_bw-max_upload_bw,max_seed_bw)

        #print used_upload_bw,used_seed_bw,used_bw
        #print max_upload_bw,max_seed_bw,max_bw

        distribute_step = 5

        if used_seed_bw < max_seed_bw:
            avail_bw = max_seed_bw-used_seed_bw
            change_rates(completes,+avail_bw)
            #for j in completes:
            #    j.change_rate(+avail_bw)
        else:
            avail_bw = used_seed_bw-max_seed_bw
            avg_bw = avail_bw/max(len(completes),1)
            compl = completes[:]
            compl.sort()
            distribute_rate(compl,avail_bw,avg_bw,distribute_step)
            #while avail_bw > 0:
            #    saved_bw = avail_bw
            #    for j in compl:
            #        if j.is_active() and j.new_rate > avg_bw:
            #            j.change_rate(-step)
            #            avail_bw -= step
            #        elif not j.is_active():
            #            j.change_rate(+avail_bw)
            #    if saved_bw == avail_bw:
            #        avg_bw -= step

        if used_upload_bw < max_upload_bw:
            avail_bw = max_upload_bw-used_upload_bw
            change_rates(incompletes,+avail_bw)
            #for j in incompletes:
            #    j.change_rate(+avail_bw)
        else:
            avail_bw = used_upload_bw-max_upload_bw
            avg_bw = avail_bw/max(len(incompletes),1)
            step = 5
            incompl = incompletes[:]
            incompl.sort()
            distribute_rate(incompl,avail_bw,avg_bw,distribute_step)
            #while avail_bw > 0:
            #    saved_bw = avail_bw
            #    for j in incompl:
            #        if j.is_active() and j.new_rate > avg_bw:
            #            j.change_rate(-step)
            #            avail_bw -= step
            #        elif not j.is_active():
            #            j.change_rate(+avail_bw)
            #    if saved_bw == avail_bw:
            #        avg_bw -= step

        all = incompletes+completes
        self.log.verbose('Upload Rate: %s\n' % repr(all))
        for j in all:
            j.apply()

    def calculate_download_rate(self):
        '''Simple download rate adjuster.  Could be enhanced with priorities.'''
        incompletes = []

        for j in self.queue.get():
            # duplicate with download rate
            #j.update_scrape()
            if not j.dow or not hasattr(j.dow.d,'downloader'):
                continue
            if j.state == STATE_RUNNING:
                incompletes.append(DownloadRateController(j))

        used_bw = sum([j.current_rate for j in incompletes])

        max_bw = float(self.policy(policy.MAX_DOWNLOAD_RATE)) or 1000000
        distribute_step = 5

        if used_bw < max_bw:
            avail_bw = max_bw-used_bw
            change_rates(incompletes,+avail_bw)
        else:
            avail_bw = used_bw-max_bw
            avg_bw = avail_bw/max(len(incompletes),1)
            incompl = incompletes[:]
            incompl.sort()
            distribute_rate(incompl,avail_bw,avg_bw,distribute_step)

        self.log.verbose('Download Rate: %s\n' % repr(incompletes))
        for j in incompletes:
            j.apply()

    def old_calculate_download_rate(self):
        '''Simple download rate adjuster.  Could be enhanced with priorities.'''
        completes = []
        incompletes = []
        used_bw = 0
        dl_rates = []
        for j in self.queue.get():
            # duplicate with upload rate
            #j.update_scrape()
            if not j.dow or not hasattr(j.dow.d,'downloader'):
                continue
            if j.state == STATE_RUNNING:
                incompletes.append(j)
                dr = j.down_rate/1000
                dl_rates.append(dr)
        max_bw = float(self.policy(policy.MAX_DOWNLOAD_RATE)) or 1000000
        active_downs=len(incompletes)
        used_bw = sum( dl_rates )
        if used_bw == 0:
            return
        average_max_bw = max_bw / active_downs
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
            dl_rates = [average_max_bw] * len(incompletes)
        for j in map(None,incompletes,dl_rates):
                j[0].dow.setDownloadRate(j[1])
    
    def terminate_seeding(self):
        now = time.time()
        for j in self.queue.get():
            pol = j.get_policy()
            if pol(policy.USE_LOCAL_POLICY):
                min_share_ratio = pol(policy.MIN_SHARE_RATIO)
                max_share_ratio = pol(policy.MAX_SHARE_RATIO)
                min_seed_time = pol(policy.MIN_SEED_TIME)
                max_seed_time = pol(policy.MAX_SEED_TIME)
                min_seeder = pol(policy.MIN_SEEDER)
                max_seeder = pol(policy.MAX_SEEDER)
                min_peer_ratio = pol(policy.MIN_PEER_RATIO)
                max_peer_ratio = pol(policy.MAX_PEER_RATIO)
            else:
                min_share_ratio = self.policy(policy.MIN_SHARE_RATIO)
                max_share_ratio = self.policy(policy.MAX_SHARE_RATIO)
                min_seed_time = self.policy(policy.MIN_SEED_TIME)
                max_seed_time = self.policy(policy.MAX_SEED_TIME)
                min_seeder = self.policy(policy.MIN_SEEDER)
                max_seeder = self.policy(policy.MAX_SEEDER)
                min_peer_ratio = self.policy(policy.MIN_PEER_RATIO)
                max_peer_ratio = self.policy(policy.MAX_PEER_RATIO)
            seed_time = now-j.finished_time

            try:
                seeder = int(j.currentseed)
            except ValueError:
                seeder = 0

            try:
                peer_ratio = seeder/int(j.currentpeer)
            except (ValueError,ZeroDivisionError):
                peer_ratio = max_peer_ratio

            if j.state == STATE_SEEDING and \
               j.share_ratio >= min_share_ratio and \
               seed_time >= min_seed_time and \
               seeder >= min_seeder and \
               peer_ratio >= min_peer_ratio and \
               (j.share_ratio >= max_share_ratio or \
                seed_time >= max_share_ratio or \
                seeder >= max_seeder or \
                peer_ratio >= max_peer_ratio):
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
            self.calculate_upload_rate()
            self.calculate_download_rate()
        except Exception,why:
            import traceback
            traceback.print_exc()
            print why
        for j in self.queue.get():
            if j.state in [STATE_RUNNING,STATE_SEEDING]:
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
