# Written by Bram Cohen
# see LICENSE.txt for license information

from time import time

class DownloaderFeedback:
    def __init__(self, choker, add_task, statusfunc, upfunc, downfunc, uptotal, downtotal,
            remainingfunc, leftfunc, file_length, finflag, interval, spewflag,
                 picker, storagewrapper):
        self.choker = choker
        self.add_task = add_task
        self.statusfunc = statusfunc
        self.upfunc = upfunc
        self.downfunc = downfunc
        self.uptotal = uptotal
        self.downtotal = downtotal
        self.remainingfunc = remainingfunc
        self.leftfunc = leftfunc
        self.file_length = file_length
        self.finflag = finflag
        self.interval = interval
        self.spewflag = spewflag
        self.picker = picker
        self.storagewrapper = storagewrapper
        self.lastids = []
        self.dist_copies = 0
        self.avg_progress = 0
        self.count = 0
        self.display()

    def _rotate(self):
        cs = self.choker.connections
        for id in self.lastids:
            for i in xrange(len(cs)):
                if cs[i].get_id() == id:
                    return cs[i:] + cs[:i]
        return cs

    def collect_spew(self):
        l = [ ]
        #cs = self._rotate()
        cs = self.choker.connections
        #self.lastids = [c.get_id() for c in cs]
        for c in cs:
            rec = {}
            rec["ip"], rec["port"] = c.get_address()
            if c is self.choker.connections[0]:
                rec["is_optimistic_unchoke"] = 1
            else:
                rec["is_optimistic_unchoke"] = 0
            if c.is_locally_initiated():
                rec["initiation"] = "Local"
            else:
                rec["initiation"] = "Remote"
            u = c.get_upload()
            rec["upload"] = (int(u.measure.get_rate()), u.is_interested(), u.is_choked())

            d = c.get_download()
            rec["download"] = (int(d.measure.get_rate()), d.is_interested(), d.is_choked(), d.is_snubbed())

            rec['utotal'] = d.connection.upload.measure.get_total()
            rec['dtotal'] = d.connection.download.measure.get_total()
            rec['completed'] = float (float (len(d.connection.download.have)-d.connection.download.unhave)/float(len(d.connection.download.have)))
            rec['peerid'] = c.get_id()
            rec['havelist'] = c.get_have_bitfield()
            l.append(rec)
        return l

    def display(self):
        self.add_task(self.display, self.interval)
        spew = []
        timeEst = self.remainingfunc()

        if self.file_length > 0:
            fractionDone = (self.file_length - self.leftfunc()) / float(self.file_length)
        else:
            fractionDone = 1

        if (self.count % 10) == 0:
            numavail = self.picker.get_numavail()
            self.avg_progress = 0
            largest = 0
            smallest = 2**31
            sum = 0
            
            for i in numavail:
                if i == None:
                    continue
                else:
                    sum += i
                if i > largest:
                    largest = i
                if i < smallest:
                    smallest = i
            
            self.dist_copies = smallest
            if largest > 0:
                self.avg_progress = (float(sum) / len(numavail)) / largest

        activity = "Downloading"

        if self.finflag.isSet():
            drate = 0.0
        else:
            drate = self.downfunc()
            
        status = {
            "activity"      : activity, 
            "fractionDone"  : fractionDone, 
            "downRate"      : drate, 
            "upRate"        : self.upfunc(),
            "upTotal"       : self.uptotal(),
            "downTotal"     : self.downtotal(),
            "havelist"      : self.storagewrapper.get_have_list(),
            "dist_copies"   : self.dist_copies,
            "avg_progress"  : self.avg_progress,
            "availlist"     : self.picker.get_numavail()
            }
            
        if timeEst is not None:
            status['timeEst'] = timeEst
        if self.spewflag.isSet():
            status['spew'] = self.collect_spew()

        self.statusfunc(status)
