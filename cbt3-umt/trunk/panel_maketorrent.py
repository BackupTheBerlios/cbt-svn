# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl (based on bittorrent & g3torrent source)
# RCS-ID:	   $Id: btcompletedirgui.py,v 1.5 2004/05/18 22:49:18 vvuser Exp $
#-----------------------------------------------------------------------------

from sys import argv, version

from BitTorrent.btcompletedir import completedir
from threading import Event, Thread
from os.path import join
from wxPython.wx import *
import wx
from traceback import print_exc

from base64 import encodestring, decodestring

from BitQueue import policy
from images import Images
import Pyro.core
from cbt_vars import *
import string

wx.EVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
	win.Connect(-1, -1, wx.EVT_INVOKE, func)

class InvokeEvent(wxPyEvent):
	def __init__(self, func, args, kwargs):
		wx.PyEvent.__init__(self)
		self.SetEventType(wx.EVT_INVOKE)
		self.func = func
		self.args = args
		self.kwargs = kwargs

class DropTarget(wx.FileDropTarget):
	def __init__(self, window):
		wx.FileDropTarget.__init__(self)
		self.win = window
	
	def OnDropFiles(self, x, y, filenames):
		for file in filenames:
			files = self.win.dirCtl.GetLabel()
			if files != '':
				self.win.dirCtl.SetLabel("%s;%s" % (files, file))
			else:
				self.win.dirCtl.SetLabel(file)
			
class PanelMakeTorrent(wx.MDIChildFrame):
	def __init__(self, parent, id, addtorrentfunc=None):

		#~ wx.MDIChildFrame.__init__(self, parent, -1, 'Nowy torrent', size = wx.Size(400, 420), pos=wx.DefaultPosition, style= wx.MINIMIZE_BOX | wx.CLOSE_BOX | wx.SYSTEM_MENU | wx.CAPTION | wx.STAY_ON_TOP)
		wx.MDIChildFrame.__init__(self, parent, id, title="Nowy torrent", size = (400,420), style = wx.MINIMIZE_BOX | wx.SYSTEM_MENU | wx.CAPTION)
		#~ self.Center(wx.BOTH)
		
		self.AddTorrent = addtorrentfunc
		self.parent = parent
		
		self.images = Images(".")
		self.SetIcon(self.images.GetImage("icn_crt"))
		
		panel = wx.Panel(self, -1)
		dt = DropTarget(self)
		self.SetDropTarget(dt)
		
		gridSizer = wx.FlexGridSizer(cols = 1, vgap = 8, hgap = 8)
		gridSizer.AddGrowableCol(0)

		self.dirCtl = wx.TextCtrl(panel, -1, '')
		
		filebox = wx.StaticBox(panel, -1, "Plik lub katalog źródłowy (wybierz lub przeciągnij i upuść tutaj)")
		fileboxer = wx.StaticBoxSizer(filebox, wx.VERTICAL)
		annbox = wx.StaticBox(panel, -1, "URL trackera")
		annboxer = wx.StaticBoxSizer(annbox, wx.VERTICAL)
		commentbox = wx.StaticBox(panel, -1, "Komentarz (opcjonalnie)")
		commentboxer = wx.StaticBoxSizer(commentbox, wx.VERTICAL)
		piecebox = wx.StaticBox(panel, -1, "Rozmiar części")
		pieceboxer = wx.StaticBoxSizer(piecebox, wx.VERTICAL)
		
		b = wx.BoxSizer(wx.HORIZONTAL)
		button = wx.Button(panel, -1, 'Utwórz z pliku')
		b.Add(button, 0, wx.EXPAND)
		EVT_BUTTON(self, button.GetId(), self.select)
		#~ b.Add(5, 5, 0, wx.EXPAND)
		c = wx.Button(panel, -1, 'Utwórz z katalogu')
		b.Add(c, 0, wx.EXPAND)
		EVT_BUTTON(self, c.GetId(), self.selectdir)
		
		
		fileboxer.Add(self.dirCtl, 1, wx.EXPAND|wx.TOP, 2)
		fileboxer.Add((-1,5))
		fileboxer.Add(b, 1, wx.EXPAND)
		gridSizer.Add(fileboxer, 1, wx.EXPAND)

		try:
			p = policy.get_policy()
			value = p(policy.CBT_TRACKER)
		except:
			value = 'http://'+tracker_host+':'+str(tracker_port)+'/announce'
		
		self.annCtl = wxTextCtrl(panel, -1, value)
		annboxer.Add(self.annCtl, 1, wx.EXPAND|wx.TOP, 2)
		gridSizer.Add(annboxer, 1, wx.EXPAND)

		self.commentCtl = wx.TextCtrl(panel, -1, '', style=wx.TE_MULTILINE)
		commentboxer.Add(self.commentCtl, 1, wx.EXPAND|wx.TOP, 2)
		gridSizer.Add(commentboxer, 1, wx.EXPAND)
		
		self.piece_length = wx.Choice(panel, -1, choices = ['2048 KB', '1024 KB', '512 KB', '256 KB', '128 KB'])
		self.piece_length.SetSelection(2)
		pieceboxer.Add(self.piece_length, 1, wx.EXPAND|wx.TOP, 2)
		gridSizer.Add(pieceboxer, 1, wx.EXPAND)

		#------------------------------------------------------------
		
		catbox = wx.StaticBox(panel, -1, "Ustawienia dodatkowe")
		catboxer = wx.StaticBoxSizer(catbox, wx.VERTICAL)
		
		self.cat_list_choices = ['mp3 (ep)', 'mp3 (cd)', 'mp3 (mix)', 'video', 'nasze wypociny', 'programy', 'inne']
		self.cat_list = wx.Choice(panel, -1, choices = self.cat_list_choices)
		self.cat_list.SetSelection(0)
		
		self.upl_list_choices = ['Nie publikuj torrenta', 'Torrent publiczny', 'Torrent prywatny']
		self.upl_list = wx.Choice(panel, -1, choices = self.upl_list_choices)
		self.upl_list.SetSelection(0)
		
		catboxer.Add(self.upl_list, 4, wx.EXPAND|wx.TOP, 4)
		catboxer.Add(self.cat_list, 4, wx.EXPAND|wx.TOP, 4)
		gridSizer.Add(catboxer, -1, wx.EXPAND)
		
		#------------------------------------------------------------
		
		buttons = wxBoxSizer(wx.HORIZONTAL)
		self.nextbutt = wx.Button(panel, -1, 'Dalej')
		EVT_BUTTON(self, self.nextbutt.GetId(), self.complete)
		self.cancelbutt = wx.Button(panel, -1, 'Zamknij')
		EVT_BUTTON(self, self.cancelbutt.GetId(), self.cancel)
		#border.Add(b2, 0, wxALIGN_CENTER | wxSOUTH, 20)
		buttons.Add(self.nextbutt)
		buttons.Add(self.cancelbutt)
		gridSizer.Add(buttons, 1, wx.ALIGN_CENTER)
		
		border = wx.BoxSizer(wx.VERTICAL)
		border.Add(gridSizer, 0, wx.EXPAND | wx.ALL, 8)
		#~ border.Add(10, 10, 1, wx.EXPAND)

		panel.SetSizer(border)
		panel.SetAutoLayout(True)
	
	def cancel(self, event):
		self.Destroy()
	
	def select(self, x):
		dl = wx.FileDialog(self, "Wybierz pliki", '/', "", '*.*', wx.OPEN | wx.MULTIPLE)
		if dl.ShowModal() == wx.ID_OK:
			x = self.dirCtl.GetValue() + ';' + ';'.join(dl.GetPaths())
			if x[0] == ';':
				x = x[1:]
			self.dirCtl.SetValue(x)

	def selectdir(self, x):
		dl = wx.DirDialog(self, 'Wybierz katalog', '/')
		if dl.ShowModal() == wx.ID_OK:
			x = self.dirCtl.GetValue() + ';' + dl.GetPath()
			if x[0] == ';':
				x = x[1:]
			self.dirCtl.SetValue(x)

	def complete(self, x):
		if self.dirCtl.GetValue() == '':
			dlg = wx.MessageDialog(self, message = 'Nie wybrałeś żadnego pliku lub katalogu.', 
				caption = 'Error', style = wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
			return
		try:
			ps = 21 - self.piece_length.GetSelection()
			files = self.dirCtl.GetValue().split(';')
			for i in range(0, len(files)):
				files[i] = files[i].encode('latin-1')
				
			announce = self.annCtl.GetValue().encode('latin-1')
			comment = self.commentCtl.GetValue().encode('latin-1')
			
			cls = self.cat_list.GetSelection()
			uls = self.upl_list.GetSelection()
			
			self.nextbutt.Enable(false)
			self.cancelbutt.Enable(false)
			
			CompleteDir(self, files, announce, ps, comment, self.AddTorrent, cls, uls, userid=self.parent.userid)
		except:
			print_exc()

class CompleteDir(PanelMakeTorrent):
	def __init__(self, parent, d, a, pl, comment, addtorrentfunc=None, cls=None, uls=None, userid=None):
		self.AddTorrent = addtorrentfunc
		self.parent = parent
		self.comment = comment
		self.responsefile = ""
		self.d = d
		self.a = a
		self.pl = pl
		self.flag = Event()
		self.uls = uls
		self.cls = cls
		self.userid = userid
		frame = wx.Frame(None, -1, 'Tworzenie torrenta', size = wx.Size(400, 150))
		self.frame = frame

		panel = wxPanel(frame, -1)

		gridSizer = wxFlexGridSizer(cols = 1, vgap = 8, hgap = 8)
		self.currentLabel = wxStaticText(panel, -1, 'Sprawdzam rozmiar plików')
		gridSizer.Add(self.currentLabel, 0, wx.EXPAND)
		self.gauge = wxGauge(panel, -1, range = 1000, style = wx.GA_SMOOTH)
		gridSizer.Add(self.gauge, 0, wx.EXPAND)
		#~ gridSizer.Add(10, 10, 1, wx.EXPAND)
		self.button = wxButton(panel, -1, 'Przerwij', size=(120,-1))
		gridSizer.Add(self.button, 0, wx.ALIGN_CENTER)
		gridSizer.AddGrowableRow(2)
		gridSizer.AddGrowableCol(0)

		g2 = wxFlexGridSizer(cols = 1, vgap = 8, hgap = 8)
		g2.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 8)
		g2.AddGrowableRow(0)
		g2.AddGrowableCol(0)
		panel.SetSizer(g2)
		panel.SetAutoLayout(True)
		EVT_BUTTON(frame, self.button.GetId(), self.done)
		EVT_CLOSE(frame, self.done)
		EVT_INVOKE(frame, self.onInvoke)
		frame.Show(True)
		Thread(target = self.complete).start()

	def complete(self):
		
		#d2 = self.btconfig['completed_tor_dir']+"/"+f+'.torrent'
		
		p = policy.get_policy()
		path = p(policy.TORRENT_PATH)
		
		a = string.split(string.join(self.d), '\\')
		a.reverse()
		self.d2 = path+"\\"+a[0]+'.torrent'
		#~ print self.d2
		
		try:
			completedir(self.d, self.a, self.flag, self.valcallback, self.filecallback, self.pl, comment=self.comment, f2=self.d2)
			if not self.flag.isSet():
				self.currentLabel.SetLabel('Zrobione!')
				self.gauge.SetValue(1000)
				self.button.SetLabel('Uploaduj torrenta')
		except (OSError, IOError), e:
			self.currentLabel.SetLabel('Error!')
			self.button.SetLabel('Zamknij')
			dlg = wx.MessageDialog(self.frame, message = 'Error - ' + str(e), 
				caption = 'Error', style = wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()

	def valcallback(self, amount):
		self.invokeLater(self.onval, [amount])

	def onval(self, amount):
		self.gauge.SetValue(int(amount * 1000))

	def filecallback(self, f):
		self.invokeLater(self.onfile, [f])

	def onfile(self, f):
		
		#self.responsefile = join(d2, f) + '.torrent'
		self.responsefile = self.d2
		#self.currentLabel.SetLabel('building ' + join(d2, f) + '.torrent')
		self.currentLabel.SetLabel('Budowanie ' + self.d2)

	def onInvoke(self, event):
		if not self.flag.isSet():
			apply(event.func, event.args, event.kwargs)

	def invokeLater(self, func, args = [], kwargs = {}):
		if not self.flag.isSet():
			wx.PostEvent(self.frame, InvokeEvent(func, args, kwargs))

	def done(self, event):
	
		self.flag.set()
		self.frame.Destroy()
		if self.currentLabel.GetLabel() == 'Zrobione!':
			if self.AddTorrent != None:
				self.UploadTorrent(self.responsefile, self.cls, self.uls)
				self.AddTorrent(self.responsefile)
			self.parent.Destroy()

	def UploadTorrent(self, rsp, cls, uls):
	
		from BitTorrent.download import Download
		from BitTorrent.bencode import bencode, bdecode
		from sha import sha
		
		if uls == 0:
			return
			
		if uls == 1:
			flag = 'pub'
		elif uls == 2:
			flag = 'prv'
	
		f = open(rsp, "rb")
		a = f.read()
		f.close()
		
		d = Download()
		rd = d.ParseResponseFile(rsp)
		
		infohash = sha(bencode(rd['info'])).hexdigest()

		p = policy.get_policy()

		try:
			cBTS = Pyro.core.getProxyForURI(pyroloc)
			status = cBTS.TorrentUpload(p(policy.CBT_LOGIN), p(policy.CBT_PASSWORD), {'tdata': a, 'tname':rsp, 'type': flag, 'hash': infohash, 'cat': cls}, self.userid )

			if status['status']:
				self.parent.parent.log.AddMsg('MakeTorrent', 'Upload torrenta zakonczony.', 'info')
			else:
				self.parent.parent.log.AddMsg('MakeTorrent', 'Błąd: ' + str(status['msg']), 'error')

			dlg = wx.MessageDialog(self.frame, message = status['msg'], caption = 'Info', style = wx.OK | wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
			
		except Exception, e:
			dlg = wx.MessageDialog(self.frame, message = 'Error - ' + str(e), caption = 'Error', style = wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
