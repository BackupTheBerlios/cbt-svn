#!/usr/bin/env python

# Written by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

from BitTornado.download_bt1 import BT1Download,defaults
from BitTornado.RawServer import RawServer,UPnP_ERROR
from BitTornado.RateLimiter import RateLimiter
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.parsedir import parsedir
from BitTornado.natpunch import UPnP_test
from BitTornado.parseargs import parseargs

import copy
from random import seed,randrange
from socket import error as socketerror
from threading import Event
from sys import argv, exit
import sys, os
from BitTornado.clock import clock
from __init__ import createPeerID, mapbase64, version
from threading import Event,Thread
from cStringIO import StringIO

import policy
from queue import hours as fmttime
from i18n import *

try:
    True
except:
    True = 1
    False = 0

class SaveAsError(Exception): pass
class InitFilesError(Exception): pass

class SingleDownload:
    def __init__(self, controller, item, hash, response, config, myid,
                 listen_port=None):
        self.controller = controller
        self.item = item
        self.hash = hash
        self.response = response
        self.config = config
        
        self.doneflag = self.item.done_flag
        self.doneflag.clear()
        self.waiting = True
        self.checking = False
        self.working = False
        self.seed = False

        self.status_msg = ''
        self.status_err = ['']
        self.status_errtime = 0
        self.status_done = 0.0

        self.rawserver = controller.handler.newRawServer(hash, self.doneflag)

        d = BT1Download(self.display, self.finished, self.error,
                        controller.exchandler, self.doneflag, config, response,
                        hash, myid, self.rawserver,
                        listen_port or controller.listen_port)
        self.d = d

        for attr in ['getResponse','reannounce',
                     'setInitiate','setConns','setUploadRate',
                     'setDownloadRate','Pause','Unpause','set_super_seed']:
            setattr(self,attr,(getattr(d,attr)))

    def deleteTorrentData(self):
        self.d.appdataobj.deleteTorrentData(self.d.infohash)

    def start(self):
        if not self.d.saveAs(self.saveAs):
            self._shutdown()
            raise SaveAsError,self.status_err[-1]
        self._hashcheckfunc = self.d.initFiles()
        if not self._hashcheckfunc:
            self._shutdown()
            raise InitFilesError,self.status_err[-1]

        self.controller.hashchecksched(self.hash)
        print 'started download',self.item.id

    def saveAs(self, name, length, saveas, isdir):
        return self.controller.saveAs(self.hash, name, saveas, isdir)

    def hashcheck_start(self, donefunc):
        if self.is_dead():
            self._shutdown()
            return
        self.waiting = False
        self.checking = True
        self._hashcheckfunc(donefunc)

    def hashcheck_callback(self):
        self.checking = False
        if self.is_dead():
            self._shutdown()
            return
        if not self.d.startEngine(ratelimiter = self.controller.ratelimiter, banfunc = self.controller.banfunc):
            self._shutdown()
            return

        self.d.upmeasure.total = self.item.old_ulsize
        self.d.downmeasure.total = self.item.old_dlsize
        size_done = self.d.storagewrapper.total_length- \
                    self.d.storagewrapper.amount_left
        if self.d.downmeasure.total < size_done:
            self.d.downmeasure.total = size_done
        del size_done

        self.d.startRerequester()
        self.statsfunc = self.d.startStats()
        self.rawserver.start_listening(self.d.getPortHandler())
        self.working = True

    def is_dead(self):
        return self.doneflag.isSet()

    def _shutdown(self):
        self.shutdown(False)

    def shutdown(self,quiet=True):
        self.doneflag.set()
        self.rawserver.shutdown()
        if self.checking or self.working:
            self.d.shutdown()
        self.waiting = False
        self.checking = False
        self.working = False
        self.controller.was_stopped(self.hash)
        if not quiet:
            self.controller.died(self.hash)
        print 'terminated download',self.item.id


    def display(self, activity = None, fractionDone = None):
        # really only used by StorageWrapper now
        if activity:
            self.status_msg = activity
        if fractionDone is not None:
            self.status_done = float(fractionDone)

    def finished(self):
        self.seed = True
        if hasattr(self.item,'cb_finished'):
            self.item.cb_finished(self.item)
        self.item.state = STATE_SEEDING
        self.item.activity = None
        self.item.clear_stat()

    def error(self, msg):
        if self.doneflag.isSet():
            self._shutdown()
        self.status_err.append(msg)
        self.status_errtime = clock()


class LaunchManyThread(Thread):
    def __init__(self,output,args=[],banfunc=None):
        Thread.__init__(self)

        self.output = output
        config,args = parseargs(args,defaults,0,0)
        self.config = config
        self.banfunc = banfunc
        self.policy = policy.get_policy()

        #self.torrent_dir = config['torrent_dir']
        #self.torrent_cache = {}
        #self.file_cache = {}
        #self.blocked_files = {}
        #self.scan_period = config['parse_dir_interval']
        self.stats_period = config['display_interval']

        self.torrent_list = []
        self.downloads = {}
        self.counter = 0
        self.doneflag = Event()

        self.hashcheck_queue = []
        self.hashcheck_current = None

        self.rawserver = RawServer(self.doneflag, config['timeout_check_interval'],
                          config['timeout'], ipv6_enable = config['ipv6_enabled'],
                          failfunc = self.failed, errorfunc = self.exchandler)

        self.upnp = UPnP_test(self.policy(policy.UPNP_NAT_ACCESS))

        while True:
            try:
                if self.policy(policy.USE_SINGLE_PORT):
                    self.listen_port = self.rawserver.find_and_bind(
                                    config['minport'], config['maxport'], config['bind'],
                                    ipv6_socket_style = config['ipv6_binds_v4'],
                                    upnp = self.upnp,
                                    randomizer = self.policy(policy.RANDOM_PORT))
                else:
                    self.listen_port = None
                break
            except socketerror, e:
                if self.upnp and e == UPnP_ERROR:
                    self.output.message('WARNING: COULD NOT FORWARD VIA UPnP')
                    self.upnp = 0
                    continue
                self.failed("Couldn't listen - " + str(e))
                return

        #self.ratelimiter = RateLimiter(self.rawserver.add_task,
        #                               config['upload_unit_size'])
        #self.ratelimiter.set_upload_rate(config['max_upload_rate'])
        self.ratelimiter = None

        self.handler = MultiHandler(self.rawserver, self.doneflag)
        seed(createPeerID())
#        self.rawserver.add_task(self.scan, 0)
        self.rawserver.add_task(self.stats, 0)

        #for hash in self.torrent_list:
        #    self.Output.message('dropped "'+self.torrent_cache[hash]['path']+'"')
        #    self.downloads[hash].shutdown()


#    def scan(self):
#        self.rawserver.add_task(self.scan, self.scan_period)
#                                
#        r = parsedir(self.torrent_dir, self.torrent_cache,
#                     self.file_cache, self.blocked_files,
#                     return_metainfo = True, errfunc = self.Output.message)
#
#        ( self.torrent_cache, self.file_cache, self.blocked_files,
#            added, removed ) = r
#
#        for hash, data in removed.items():
#            self.Output.message('dropped "'+data['path']+'"')
#            self.remove(hash)
#        for hash, data in added.items():
#            self.Output.message('added "'+data['path']+'"')
#            self.add(hash, data)

    def run(self):
        try:
            self.handler.listen_forever()
        except:
            import traceback
            data = StringIO()
            traceback.print_exc(file=data)
            self.output.exception(data.getvalue())
            self.output.restart()
        if not self.rawserver.doneflag.isSet():
            self.output.restart()

    def stats(self):            
        self.rawserver.add_task(self.stats, self.stats_period)
        data = []
        for hash in self.torrent_list:
            item = self.downloads[hash]
            name,size = item.title,item.size
            #name = cache['path']
            #size = cache['length']
            d = item.dow
            if not d:
                continue
            progress = 0.0
#            peers = 0
#            seeds = 0
#            seedsmsg = "S"
            uprate = 0.0
            dnrate = 0.0
#            upamt = 0
#            dnamt = 0
            t = 0
            spew = None
            s = None
            if d.is_dead():
                status = _('stopped')
            elif d.waiting:
                status = _('waiting for hash check')
            elif d.checking:
                status = d.status_msg
                progress = d.status_done
#                progress = '%.1f%%' % (d.status_done*100)
            else:
                stats = d.statsfunc()
                s = stats['stats']
                spew = stats['spew']
                if d.seed:
                    status = ''
#                    progress = '100.0%'
#                    seeds = s.numOldSeeds
#                    seedsmsg = "s"
                else:
                    if s.numSeeds + s.numPeers:
                        t = stats['time']
                        if t is None:
                            t = -1 
#                        if t == 0:  # unlikely
#                            t = 0.01
                        status = ''
                    else:
                        t = -1
                        status = _('connecting to peers')
                    progress = stats['frac']
#                    progress = '%.1f%%' % (int(stats['frac']*1000)/10.0)
#                    seeds = s.numSeeds
                    dnrate = stats['down']
#                peers = s.numPeers
                uprate = stats['up']
#                upamt = s.upTotal
#                dnamt = s.downTotal
                   
            if d.is_dead() or d.status_errtime+300 > clock():
                msg = d.status_err[-1]
            else:
                msg = ''

#            data.append(( name, status, progress, peers, seeds, seedsmsg,
#              uprate, dnrate, upamt, dnamt, size, t ))
            item.update_info(fractionDone=progress,
                             timeEst=t,
                             downRate=dnrate,
                             upRate=uprate,
                             activity=status,
                             statistics=s,
                             spew=spew)
            item.error = msg

    def remove(self, item):
        hash = item.infohash_bin

        try:
            self.torrent_list.remove(hash)
        except ValueError:
            pass
        try:
            self.downloads[hash].dow.shutdown()
            del self.downloads[hash]
        except (KeyError,AttributeError):
            pass
        if item.listen_port:
            item.listen_port = None
        del item.dow
        item.dow = None

    def add(self, item):
        hash,data = item.infohash_bin,item.get_meta()

        self.torrent_list.append(hash)
        self.downloads[hash] = item

        c = self.counter
        self.counter += 1
        x = ''
        for i in xrange(3):
            x = mapbase64[c & 0x3F]+x
            c >>= 6
        peer_id = createPeerID(x)
        if not self.policy(policy.USE_SINGLE_PORT):
            minport = self.policy(policy.MIN_PORT)
            maxport = self.policy(policy.MAX_PORT)
            maxport = max(minport,maxport)

            listen_port = self.rawserver.find_and_bind(
                          minport, maxport,
                          self.policy(policy.BIND_IP),
                          ipv6_socket_style = self.policy(policy.IPV6_BINDS_V4),
                          upnp = self.upnp,
                          randomizer = self.policy(policy.RANDOM_PORT))
        else:
            listen_port = None

        config = copy.copy(self.config)
        config['saveas'] = item.dest_path
        config['spew'] = 1
        config['min_peers'] = self.policy(policy.MIN_PEER)
        config['max_connections'] = self.policy(policy.MAX_PEER)
        config['max_initiate'] = self.policy(policy.MAX_INITIATE)
        config['rerequest_interval'] = self.policy(policy.REREQUEST_INTERVAL)
        try:
            d = SingleDownload(self,item,hash,data,
                               config,peer_id,listen_port)

            item.dow = d
            item.listen_port = listen_port
            if item.recheck:
                d.deleteTorrentData()
                item.recheck = 0
            d.start()
        except Exception,why:
            import traceback
            traceback.print_exc()
            self.remove(item)
            self.exchandler(why)

    def stop(self, item=None):
        if not item:
            for hash in self.torrent_list:
                item = self.downloads[hash]
                self.remove(item)
            self.rawserver.doneflag.set()
        else:
            item.done_flag.set()

    def set_upload_rate(self,rate,item=None):
        if not item:
            pass
            #self.ratelimiter.set_upload_rate(rate)
        else:
            item.dow.setUploadRate(rate)

    def set_download_rate(self,rate,item=None):
        if not item:
            pass
            #for hash in self.torrent_list:
            #    item = self.downloads[hash]
            #    item.dow.setDownloadRate(rate)
        else:
            item.dow.setDownloadRate(rate)

    def saveAs(self, hash, name, saveas, isdir):
        item = self.downloads[hash]
#        if saveas:
#            saveas = os.path.join(saveas,x['file'][:-1-len(x['type'])])
#        else:
#            saveas = x['path'][:-1-len(x['type'])]
        if isdir and not os.path.isdir(saveas):
            try:
                os.mkdir(saveas)
            except:
                raise OSError("couldn't create directory for "+item.title)
        return saveas

    def hashchecksched(self, hash):
        self.hashcheck_queue.append(hash)
        if not self.hashcheck_current:
            self._hashcheck_start()

    def _hashcheck_start(self):
        try:
            self.hashcheck_current = self.hashcheck_queue.pop(0)
            self.downloads[self.hashcheck_current].dow.hashcheck_start(self.hashcheck_callback)
        except IndexError:
            pass

    def hashcheck_callback(self):
        self.downloads[self.hashcheck_current].dow.hashcheck_callback()
        if self.hashcheck_queue:
            self._hashcheck_start()
        else:
            self.hashcheck_current = None

    def died(self, hash):
        try:
            item = self.downloads[hash]
            self.output.message('DIED: '+item.id)
        except KeyError:
            self.failed('%s has not been started properly' % hash)

    def was_stopped(self, hash):
        try:
            self.hashcheck_queue.remove(hash)
        except:
            pass
        if self.hashcheck_current == hash:
            self._hashcheck_start()

    def failed(self, s):
        self.output.message('FAILURE: '+s)

    def exchandler(self, s):
        self.output.exception(str(s))

