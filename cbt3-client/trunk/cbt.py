# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: cbt.py 108 2004-08-31 00:29:20Z warp $
#-----------------------------------------------------------------------------

from cbt_vars import PSYCO
if PSYCO:
	try:
		import psyco
		assert psyco.__version__ >= 0x010100f0
		psyco.full()
	except:
		print "psyco import failed"
		pass 

import wx, os.path, sys, thread

from threading import Timer
from images import Images

from cbt_vars import *
from cbt_widgets import *
from cbt_jabber import CbtJabber

from panel_transfers import PanelTransfers
from panel_mytorrents import PanelMyTorrents
from panel_chat import PanelChat
from panel_public import PanelPublic
from panel_options import PanelOptions
from panel_transfer_details import PanelTransferDetails
from panel_log import PanelLog
from panel_maketorrent import PanelMakeTorrent

from BitQueue import policy
from BitQueue.manager import Console
from BitQueue.webservice import WebServiceServer, WebServiceRequestHandler
from BitQueue import version as btqver

import Pyro.core
import rotor

class ParentFrame(wx.MDIParentFrame):
	def __init__(self):
		wx.MDIParentFrame.__init__(self, None, -1, prog_name_full, size=(760,580), style = wx.DEFAULT_FRAME_STYLE)
		
		ID_New  = wx.NewId()
		ID_Exit = wx.NewId()
		ID_Navbar = wx.NewId()
		
		self.rt = rotor.newrotor('cbtcbt', 12)
		self.userid = None
		
		#~ self.Maximize()

		# icons init
		
		self.images = Images(".")
		self.SetIcon(self.images.GetImage('icn_cbt'))
		self.windows = {"transfers":0, "chat":0, "public":0, "my":0, "options":0, "maketorrent":0}
		self.windowsi = {}
		self.tdwindows = {}
		
		# btq init
		
		if sys.platform == 'win32' or not os.environ.get('HOME'):
			root_path = os.path.dirname(os.path.abspath(sys.argv[0]))
		else:
			root_path = os.path.join(os.environ.get('HOME'),'.cbt')

		self.pol = policy.Policy(root_path)
		self.pol.set_default()

		self.btq = CbtBTQ()
		self.btq.controller.start()
		self.btq.queue.start()
		self.btq.webservice = WebServiceServer(WebServiceRequestHandler, self.btq.queue)
		self.btq.webservice.start()
		
		self.cBTS = Pyro.core.getProxyForURI(pyroloc)

		# menu
		
		menu = wx.Menu()
		menu.Append(ID_Exit, "E&xit")
		
		menubar = wx.MenuBar()
		menubar.Append(menu, "&File")
		self.SetMenuBar(menubar)
		
		self.CreateStatusBar()
		
		self.Bind(wx.EVT_MENU, self.OnExit, id=ID_Exit)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_SIZE, self.OnSize)

		# main window

		self.bg_bmp = self.images.GetImage("app_bg")
		self.GetClientWindow().Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
		
		win = wx.SashLayoutWindow(self, ID_Navbar, style=wx.NO_BORDER)
		win.SetDefaultSize((158, 1000))
		win.SetOrientation(wx.LAYOUT_VERTICAL)
		win.SetAlignment(wx.LAYOUT_LEFT)
		win.SetSashVisible(wx.SASH_RIGHT, True)
		
		self.navbar = CbtNavbar(win, ID_Navbar, act=self.OnNewWindow)

		# log window
		
		self.log = PanelLog(self, -1)
		self.windows["log"] = 1
		self.log.Show(True)
		self.log.SetSize((500,320))

		# tray
		
		if (sys.platform == 'win32'):
			
			self.tray = wx.TaskBarIcon()
			self.trayicon = self.images.GetImage('icn_cbt')
			self.tray.SetIcon(self.trayicon, '')

			self.TBMENU_RESTORE = 60100
			self.TBMENU_CLOSE   = 60101
			self.iconized = False

			wx.EVT_ICONIZE(self, self.onIconify)
			wx.EVT_TASKBAR_LEFT_DCLICK(self.tray, self.onTaskBarActivate)
			wx.EVT_TASKBAR_RIGHT_UP(self.tray, self.onTaskBarMenu)
			wx.EVT_MENU(self.tray, self.TBMENU_RESTORE, self.onTaskBarActivate)
			wx.EVT_MENU(self.tray, self.TBMENU_CLOSE, self.OnClose)
			
		# login
		
		thread.start_new_thread(self._remoteLogin, ())
		thread.start_new_thread(self._jabberLogin, ())

	def _jabberLogin(self):
		try:
			self.jab = CbtJabber( {"username":self.pol(policy.CBT_LOGIN), "password":self.rt.decrypt(self.pol(policy.CBT_PASSWORD)), "server":jabserv, "resource":"cbt"} )
			self.log.AddMsg("Jabber", "Zalogowany jako: " + self.pol(policy.CBT_LOGIN), "info")
		except Exception, e:
			try:
				self.log.AddMsg("Jabber", "Got exception: " + str(e), "error")
			except:
				pass

	def _remoteLogin(self):
		try:
			remote = self.cBTS.LoginCheck(self.pol(policy.CBT_LOGIN), self.rt.decrypt(self.pol(policy.CBT_PASSWORD)))
			
			if remote['status']:
				self.log.AddMsg("cBT server", "cBTS wersja "+remote['cbts_ver']+" b"+remote['cbts_build']+": połączony.", "info")
				self.userid = remote['userid']
				self.cbt_login = self.pol(policy.CBT_LOGIN)
				self.cbt_password = self.rt.decrypt(self.pol(policy.CBT_PASSWORD))
				self.navbar.Update("all")
			elif not remote['status']:
				self.navbar.Update("pub")
				self.log.AddMsg("cBT server", "Błąd w trakcie logowania.", "error")
		except:
			try:
				self.navbar.Update("pub")
				self.log.AddMsg("cBT server", "Błąd w trakcie próby połączenia.", "error")
			except:
				pass

	def OnTransferDisplayDetails(self, evt=None, qid=None):
		try:
			a = self.tdwindows[qid]
		except:
			self.tdwindows[qid] = 0
			
		if not self.tdwindows[qid]:
			win = PanelTransferDetails(self, -1, btq=self.btq, qid=qid)
			win.Show(True)
			self.tdwindows[qid] = 1
	
	def OnSize(self, evt):
		wx.LayoutAlgorithm().LayoutMDIFrame(self)
		self.OnEraseBackground()

	def OnExit(self, evt):
		self.Close(True)
		
	def OnClose(self, evt):
		self.btq.do_quit()
		
		if (sys.platform == 'win32'):
			del self.tray

		self.Destroy()

	def OnNewWindow(self, evt):
		sel = self.navbar.GetFirstSelected()
		sel = self.navbar.GetItemData(sel)
		
		if sel == 0 and not self.windows["transfers"]:
			win = PanelTransfers(self, -1, btq=self.btq)
			self.windowsi["transfers"] = win
			self.windows["transfers"] = 1
		elif sel == 1 and not self.windows["chat"]:
			win = PanelChat(self, -1)
			self.windowsi["chat"] = win
			self.windows["chat"] = 1
		elif sel == 2 and not self.windows["public"]:
			win = PanelPublic(self, -1)
			self.windowsi["public"] = win
			self.windows["public"] = 1
		elif sel == 3 and not self.windows["my"]:
			win = PanelMyTorrents(self, -1)
			self.windowsi["my"] = win
			self.windows["my"] = 1
		elif sel == 4 and not self.windows["options"]:
			win = PanelOptions(self, -1)
			self.windowsi["options"] = win
			self.windows["options"] = 1
			
		if sel == 0 and self.windows["transfers"]:
			self.windowsi["transfers"].Activate()
		elif sel == 1 and self.windows["chat"]:
			self.windowsi["chat"].Activate()
		elif sel == 2 and self.windows["public"]:
			self.windowsi["public"].Activate()
		elif sel == 3 and self.windows["my"]:
			self.windowsi["my"].Activate()
		elif sel == 4 and self.windows["options"]:
			self.windowsi["options"].Activate()
		
		try:
			win.Show(True)
		except:
			pass

	def WindowTile(self, evt):
		self.Tile()
		
	def WindowCascade(self, evt):
		self.Cascade()
		
	def WindowPrev(self, evt):
		self.ActivatePrevious()
		
	def WindowNext(self, evt):
		self.ActivateNext()

	def OnEraseBackground(self, evt=None):
		try:
			dc = evt.GetDC()
		except:
			dc = wx.ClientDC(self.GetClientWindow())
		
		sz = self.GetClientSize()
		w = self.bg_bmp.GetWidth()
		h = self.bg_bmp.GetHeight()
		x = 0
		
		while x < sz.width:
			y = 0
		
			while y < sz.height:
				dc.DrawBitmap(self.bg_bmp, x, y, 0)
				y = y + h
		
			x = x + w
			
		self._drawTxt(dc, prog_name_full, 10, 0, 24)
		self._drawTxt(dc, "based on " + btqver, 8, 0, 12)
		self._drawTxt(dc, 'Python ' + sys.version.split()[0] + " + wxWidgets " + wx.VERSION_STRING, 8, 0, 0)
		
	def _drawTxt(self, dc, txt, size, x, y):
		sz = self.GetClientSize()
		
		font = wx.Font(size, wx.SWISS, wx.NORMAL, wx.BOLD)
		dc.SetTextForeground(wx.Colour(255,255,255))
		dc.SetFont(font)
		
		ent = dc.GetTextExtent(txt)
		dc.DrawText(txt, sz.width - ent[0] - 168 - x, sz.height - ent[1] - 5 - y)

	# tray

	def onIconify(self, evt):
		try:
			self.Hide()
			wx.EVT_ICONIZE(self, self.onIconifyDummy)
			if self.iconized:
				#~ self.frame.Iconize(False)
				self.iconized = False
			else:
				#~ self.frame.Iconize(True)
				self.iconized = True
			wx.EVT_ICONIZE(self, self.onIconify)
		except:
			print "err"
			
	def onIconifyDummy(self, evt):
		return

	def onTaskBarActivate(self, evt):
		try:
			if self.IsIconized():
				self.Iconize(False)
				self.Raise()
			if not self.IsShown():
				self.Show(True)
				self.Raise()
			#~ self.tray.RemoveIcon()
		except:
			pass

	def onTaskBarMenu(self, evt):
		menu = wx.Menu()
		menu.Append(self.TBMENU_RESTORE, "Pokaż głowne okno")
		menu.Append(self.TBMENU_CLOSE,   "Zamknij")
		self.tray.PopupMenu(menu)
		menu.Destroy()


class CbtBTQ(Console):
	
	def CbtList(self,line=None):
		dataf = []
		for j in self.queue.jobs():
			data = j.get()
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
			data2 = vars(j)
			data['msg'] = data2['activity']
			
			dataf.append(data)
			
		return dataf
		
	def CbtSpew(self,line):
		if not line:
			return
		j = self.queue.job(line)
		if not j:
			return
		spew = j.get_spew()
		dataf = []
		for i in spew:
			var = {}
			var.update(i)
			try:
				var['cc'],var['netname'] = self.ipdb[i['ip']].split(':')
			except (IndexError,TypeError,KeyError,AssertionError):
				var['cc'],var['netname'] = 'XX','Unknown'
			#~ var['client'] = var['client']
			#~ var['netname'] = var['netname']
			dataf.append(var)
			
		return dataf
		
	def CbtStat(self,line):
		if not line:
			return
		j = self.queue.job(line)
		stat = j.statistics
		
		dataf = {}

		try:
			dataf['numcopies'] = stat.numCopies
		except:
			pass
			
		try:
			dataf['numcopies2'] = stat.numCopies2
		except:
			pass
			
		try:
			dataf['discarded'] = stat.discarded
		except:
			pass
			
		try:
			dataf['downtotal'] = stat.downTotal
		except:
			pass
			
		try:
			dataf['storage_complete'] = stat.storage_numcomplete
		except:
			pass
			
		try:
			dataf['storage_totalpieces'] = stat.storage_totalpieces
		except:
			pass
			
		try:
			dataf['uptotal'] = stat.upTotal
		except:
			pass
			
		try:
			dataf['piecescomplete'] = stat.connecter.downloader.storage.have
			dataf['numactive'] = stat.connecter.downloader.storage.numactive
		except:
			pass
		
		return {"dataf":dataf, "stat":stat}

	def CbtDetail(self,line=None):
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
		
		return data
		
#~ print '''ID:                    %(id)s
#~ Response:              %(filename)s
#~ Info Hash:             %(infohash)s
#~ Announce:              %(announce)s
#~ Peer ID:               %(peer_id)s
#~ Name:                  %(title)s
#~ Destination:           %(dest_path)s
#~ Size:                  %(totalsize)s
#~ ETA:                   %(eta)s
#~ State:                 %(btstatus)s
#~ Progress:              %(progress)s
#~ Downloaded/Uploaded:   %(dlsize)s/%(ulsize)s
#~ Share Ratio:           %(ratio)s
#~ Download/Upload Speed: %(dlspeed)s/%(ulspeed)s
#~ Total Speed:           %(totalspeed)s
#~ Peer Average Progress: %(peeravgprogress)s
#~ Peers/Seeds/Copies:    %(peers)s/%(seeds)s/%(copies)0.3f
#~ Last Error:            %(error)s
#~ ''' % data

#----------------------------------------------------------------------

if __name__ == '__main__':
	
	class MyApp(wx.App):
		def OnInit(self):
			wx.InitAllImageHandlers()
			frame = ParentFrame()
			frame.Show(True)
			self.SetTopWindow(frame)
			return True

	class TestFrame(wx.Frame):
		def __init__(self):
			wx.Frame.__init__(self, None, -1, 'Test', size = wx.Size(430, 350), style = wx.DEFAULT_FRAME_STYLE | wx.NO_FULL_REPAINT_ON_RESIZE | wx.CLIP_CHILDREN)

	app = wx.PySimpleApp()
	checker = wx.SingleInstanceChecker( prog_name + '-' + wx.GetUserId() )
	
	if len(sys.argv) == 1:

		if checker.IsAnotherRunning() == False:
			
			if sys.platform == 'win32' or not os.environ.get('HOME'):
				root_path = os.path.dirname(os.path.abspath(sys.argv[0]))
			else:
				root_path = os.path.join(os.environ.get('HOME'),'.cbt')
			
			p = policy.Policy(root_path)
			p.set_default()

			if p(policy.CBT_SHOWSPLASH):
			
				test = TestFrame()
				image = wx.Bitmap("data/splash.png")
				image.LoadFile('data/splash.png', wx.BITMAP_TYPE_PNG)
				splash = wx.SplashScreen(image, wx.SPLASH_CENTRE_ON_SCREEN | wx.SPLASH_TIMEOUT, 4000, test, -1)
		
				splashtimer = Timer(5, test.Destroy)
				splashtimer.start()
			
			app = MyApp(False)
			app.MainLoop()
			
		else:
	
			app = wx.PySimpleApp()
			frame = wx.Frame(None, -1, '')
		
			dlg = wx.MessageDialog(frame, 'Inna instancja programu jest już uruchomiona.', prog_name_long, wx.OK | wx.ICON_INFORMATION)
		
			dlg.ShowModal()
			dlg.Destroy()
			frame.Destroy()
			
	else:
		
		command = sys.argv[1]
		
		if sys.platform == 'win32' or not os.environ.get('HOME'):
			root_path = os.path.dirname(os.path.abspath(sys.argv[0]))
		else:
			root_path = os.path.join(os.environ.get('HOME'),'.btqueue')
		
		pol = policy.Policy(root_path)
		pol.set_default()
		
		if command == "add":
			btq = CbtBTQ()
			btq.controller.start()
			btq.queue.start()
			btq.do_add(' '.join(sys.argv[2:]))
			btq.do_quit()
