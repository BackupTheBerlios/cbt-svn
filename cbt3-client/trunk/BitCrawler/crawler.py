import urllib

from media import factory,List
from filter import get_filter
from loader import get_loader
from BitQueue import policy
from BitQueue.webservice import WebServiceRequest
from BitQueue.log import get_logger
import policy as cpolicy

class XMLWrapper:
    def __init__(self,file,tag='MediaList',load=1):
        self.file = policy.get_policy().get_path(file)
        if load:
            try:
                self.obj = factory.from_file(self.file)
            except IOError:
                self.obj = List(tag)
        else:
            self.obj = List(tag)

    def __getattr__(self,attr):
        if attr in ['file','obj']:
            return self.__dict__[attr]
        else:
            return getattr(self.__dict__['obj'],attr)

    def __setattr__(self,attr,value):
        if attr in ['file','obj']:
            self.__dict__[attr] = value
        else:
            setattr(self.__dict__['obj'],attr,value)

    def __delattr__(self,attr):
        if attr in ['file','obj']:
            del self.__dict__[attr]
        else:
            delattr(self.obj,attr)

    def save(self):
        fd = open(self.file,'w')
        self.obj.to_element().save(fd)
        fd.close()

class Crawler:
    def __init__(self,test_mode=0):
        self.test_mode = test_mode
        self.tracker_list = XMLWrapper(cpolicy.TRACKER_FILE,
                                       tag='TrackerList')
        self.interest_list = XMLWrapper(cpolicy.INTEREST_FILE,
                                        tag='InterestList')
        self.submitted_list = XMLWrapper(cpolicy.SUBMITTED_FILE)
        pol = policy.get_policy()
        self.webreq = WebServiceRequest((pol(policy.WEBSERVICE_IP),
                                         pol(policy.WEBSERVICE_PORT)),
                                         pol(policy.WEBSERVICE_ID))
        self.ignore_wait = pol(policy.IGNORE_WAITING_MEDIA)
        self.log = get_logger()
        self.wait_list = XMLWrapper(cpolicy.WAIT_FILE,
                                    load=(self.ignore_wait==0))
        self.failed_list = XMLWrapper(cpolicy.WAIT_FILE,
                                      load=0)

    def process_tracker(self,tracker):
        Filter = get_filter(tracker.filter)
        Loader = get_loader(tracker.loader)
        loader = Loader(tracker,Filter(self.interest_list,tracker.publisher))
        media_list = loader.fetch()
        for media in media_list:
            if not media in self.submitted_list and \
               not media in self.wait_list:
                media.fetch()
                self.wait_list.append(media)

    def process(self):
        self.preprocess()
        for tracker in self.tracker_list:
            self.process_tracker(tracker)

        for media in self.wait_list:
            if self.test_mode:
                print media
                continue
            if self.submit(media):
                self.submitted_list.append(media)
            else:
                self.failed_list.append(media)

        self.postprocess()

    def submit(self,media):
        ret = 0

        media.fetch()
        if not media.exists():
            self.log.error('submission failed: %s not exists\n' % media.title)
            return ret

        try:
            key,value = self.webreq.add(urllib.quote(media.filename()))
            if value == 'OK':
                self.log.info('%s submitted\n' % media.title)
                ret = 1
            else:
                self.log.error('submission failed: %s %s\n' % (media.title,value))
        except Exception,why:
            self.log.warn('unexpected exception: %s\n' % str(why))

        return ret

    def preprocess(self):
        pass

    def postprocess(self):
        if not self.test_mode:
            #self.tracker_list.save()
            self.failed_list.save()
            self.submitted_list.save()

if __name__ == '__main__':
    c = Crawler()
    c.process()
