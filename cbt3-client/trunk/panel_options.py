# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_options.py 110 2004-08-31 01:17:29Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys
from wxPython.xrc import *

from images import Images
from BitQueue import policy
import rotor, thread

class PanelOptions(wx.MDIChildFrame):
	def __init__(self, parent, id):
		wx.MDIChildFrame.__init__(self, parent, id, title="Opcje", size=(450,300), style = wx.MINIMIZE_BOX | wx.SYSTEM_MENU | wx.CAPTION)
		
		self.parent = parent
		self.rt = rotor.newrotor('cbtcbt', 12)
		
		self.images = Images(".")
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelOptions")
		self.SetIcon(self.images.GetImage("icn_conf"))

		self.opt_login = XRCCTRL(self, "opt_login")
		self.opt_password = XRCCTRL(self, "opt_password")
		self.btnSave = XRCCTRL(self, "btnSave")
		self.btnCancel = XRCCTRL(self, "btnCancel")
		self.btnPath1 = XRCCTRL(self, "btnPath1")
		self.btnPath2 = XRCCTRL(self, "btnPath2")
		self.opt_destdir = XRCCTRL(self, "opt_destdir")
		self.opt_torrentdir = XRCCTRL(self, "opt_torrentdir")
		self.opt_splash = XRCCTRL(self, "opt_splash")

		self.Bind(wx.EVT_BUTTON, self.OnCancel, id=XRCID("btnCancel"))
		self.Bind(wx.EVT_BUTTON, self.OnSave, id=XRCID("btnSave"))
		self.Bind(wx.EVT_BUTTON, self.OnPath1, id=XRCID("btnPath1"))
		self.Bind(wx.EVT_BUTTON, self.OnPath2, id=XRCID("btnPath2"))

		self.Bind(wx.EVT_CLOSE, self.OnClose)

		self.Activate()
		self.SetDefaults()

	def OnClose(self, evt=None):
		self.parent.windows["options"] = 0
		self.Destroy()

	def OnCancel(self, evt):
		self.OnClose()
		
	def OnSave(self, evt):
		
		if self.opt_login.GetValue() != self.deflogin or self.opt_password.GetValue() != self.defpasswd:
			self.parent.pol.update(policy.CBT_LOGIN, self.opt_login.GetValue())
			self.parent.pol.update(policy.CBT_PASSWORD, self.rt.encrypt(self.opt_password.GetValue()) )
			thread.start_new_thread(self.parent._remoteLogin, ())
			#~ thread.start_new_thread(self.parent._jabberLogin, ())
		self.parent.pol.update(policy.DEST_PATH, self.opt_destdir.GetValue())
		self.parent.pol.update(policy.TORRENT_PATH, self.opt_torrentdir.GetValue())
		self.parent.pol.update(policy.CBT_SHOWSPLASH, self.opt_splash.GetValue())
		
		#~ self.parent.pol.update(policy.MAX_UPLOAD_RATE, self.setMaxUpl.GetValue())
		#~ self.parent.pol.update(policy.MIN_SHARE_RATIO, float ( self.setMinShare.GetValue() ) / 10 )
		#~ self.parent.pol.update(policy.MAX_JOB_RUN, self.setMaxTransfer.GetValue() )
		#~ self.parent.pol.update(policy.DEST_PATH, self.setDefDir.GetValue() )
		self.parent.pol.save()
		
		self.parent.log.AddMsg('Opcje', 'Zapisano.')
		
		self.OnClose()
		
	def SetDefaults(self):
		self.deflogin = self.parent.pol(policy.CBT_LOGIN)
		self.defpasswd = self.rt.decrypt(self.parent.pol(policy.CBT_PASSWORD))
		self.opt_login.SetValue(self.parent.pol(policy.CBT_LOGIN))
		self.opt_password.SetValue(self.rt.decrypt(self.parent.pol(policy.CBT_PASSWORD)))
		self.opt_destdir.SetValue(self.parent.pol(policy.DEST_PATH))
		self.opt_torrentdir.SetValue(self.parent.pol(policy.TORRENT_PATH))
		self.opt_splash.SetValue(self.parent.pol(policy.CBT_SHOWSPLASH))

		
	def OnPath1(self, evt=None):
		try:
			a = self.SelectDir()
			self.opt_destdir.SetValue(a)
		except:
			pass
		
	def OnPath2(self, evt=None):
		try:
			a = self.SelectDir()
			self.opt_torrentdir.SetValue(a)
		except:
			pass
		
	def SelectDir(self, evt=None):
		dl = wx.DirDialog(self, 'Wybierz katalog', '/', style = wx.DD_NEW_DIR_BUTTON )
		if dl.ShowModal() == wx.ID_OK:
			x = dl.GetPath()
			return x
