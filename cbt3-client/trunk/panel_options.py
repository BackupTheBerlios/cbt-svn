#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_options.py 110 2004-08-31 01:17:29Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys
from wxPython.xrc import *

from images import Images
from BitQueue import policy
from xmlrpclib import Server
import rotor, thread

class PanelOptions(wx.MDIChildFrame):
	def __init__(self, parent, id):
		wx.MDIChildFrame.__init__(self, parent, id, title=_("Options"), size=(450,350), style = wx.MINIMIZE_BOX | wx.SYSTEM_MENU | wx.CAPTION)
		
		self.parent = parent
		self.rt = rotor.newrotor('cbtcbt', 12)
		
		self.images = Images(".")
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelOptions")
		self.SetIcon(self.images.GetImage("icn_conf"))

		self.opt_login = XRCCTRL(self, "opt_login")
		self.opt_password = XRCCTRL(self, "opt_password")
		self.opt_rpcurl = XRCCTRL(self, "opt_rpcurl")
		self.btnSave = XRCCTRL(self, "btnSave")
		self.btnCancel = XRCCTRL(self, "btnCancel")
		self.btnPath1 = XRCCTRL(self, "btnPath1")
		self.btnPath2 = XRCCTRL(self, "btnPath2")
		self.opt_destdir = XRCCTRL(self, "opt_destdir")
		self.opt_torrentdir = XRCCTRL(self, "opt_torrentdir")
		self.opt_splash = XRCCTRL(self, "opt_splash")
		self.opt_lang = XRCCTRL(self, "opt_lang")
		
		#
		
		XRCCTRL(self, "opt_notebook").SetPageText( 0, _("Base options") )
		XRCCTRL(self, "opt_notebook").SetPageText( 1, _("Engine options") )
		
		XRCCTRL(self, "opt_box1").SetLabel( _("Community settings:") )
		XRCCTRL(self, "opt_box2").SetLabel( _("GUI settings:") )
		XRCCTRL(self, "opt_box3").SetLabel( _("Paths:") )
		
		XRCCTRL(self, "opt_lab1").SetLabel( _("Login:") )
		XRCCTRL(self, "opt_lab2").SetLabel( _("Password:") )
		XRCCTRL(self, "opt_lab3").SetLabel( _("URL:") )
		XRCCTRL(self, "opt_lab4").SetLabel( _("Download dir:") )
		XRCCTRL(self, "opt_lab5").SetLabel( _("Torrents dir:") )
		XRCCTRL(self, "opt_lab6").SetLabel( _("Language:") )
		XRCCTRL(self, "opt_splash").SetLabel( _("Show splash screen") )
		
		XRCCTRL(self, "btnSave").SetLabel( _("Apply") )
		XRCCTRL(self, "btnCancel").SetLabel( _("Cancel") )
		
		XRCCTRL(self, "opt_lang").Insert( _("Polski"), 0 )
		XRCCTRL(self, "opt_lang").Insert( _("English"), 1 )
		
		#

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
		
		if self.opt_login.GetValue() != self.deflogin or self.opt_password.GetValue() != self.defpasswd or self.defrpcurl != self.opt_rpcurl.GetValue():
			self.parent.pol.update(policy.CBT_LOGIN, self.opt_login.GetValue())
			self.parent.pol.update(policy.CBT_PASSWORD, self.rt.encrypt(self.opt_password.GetValue()) )
			self.parent.pol.update(policy.CBT_RPCURL, self.opt_rpcurl.GetValue())
			
			try:
				self.parent.cBTS = Server( self.opt_rpcurl.GetValue() )
				thread.start_new_thread(self.parent._remoteLogin, ())
				#~ thread.start_new_thread(self.parent._jabberLogin, ())
			except Exception, e:
				self.parent.log.AddMsg( _('cBT server'), _('Error') + ": " + str(e), "error" )
			
		self.parent.pol.update(policy.DEST_PATH, self.opt_destdir.GetValue())
		self.parent.pol.update(policy.TORRENT_PATH, self.opt_torrentdir.GetValue())
		self.parent.pol.update(policy.CBT_SHOWSPLASH, self.opt_splash.GetValue())
		
		lang = self.opt_lang.GetSelection()
		
		if lang == 0:
			self.parent.pol.update(policy.CBT_LANG, "pl_PL")
		else:
			self.parent.pol.update(policy.CBT_LANG, "en_US")

		#~ self.parent.pol.update(policy.MAX_UPLOAD_RATE, self.setMaxUpl.GetValue())
		#~ self.parent.pol.update(policy.MIN_SHARE_RATIO, float ( self.setMinShare.GetValue() ) / 10 )
		#~ self.parent.pol.update(policy.MAX_JOB_RUN, self.setMaxTransfer.GetValue() )
		#~ self.parent.pol.update(policy.DEST_PATH, self.setDefDir.GetValue() )
		self.parent.pol.save()
		
		self.parent.log.AddMsg(_('Options'), _('Saved.'))
		
		self.OnClose()
		
	def SetDefaults(self):
		self.deflogin = self.parent.pol(policy.CBT_LOGIN)
		self.defpasswd = self.rt.decrypt(self.parent.pol(policy.CBT_PASSWORD))
		self.defrpcurl = self.parent.pol(policy.CBT_RPCURL)
		self.opt_login.SetValue(self.parent.pol(policy.CBT_LOGIN))
		self.opt_password.SetValue(self.rt.decrypt(self.parent.pol(policy.CBT_PASSWORD)))
		self.opt_rpcurl.SetValue(self.parent.pol(policy.CBT_RPCURL))
		self.opt_destdir.SetValue(self.parent.pol(policy.DEST_PATH))
		self.opt_torrentdir.SetValue(self.parent.pol(policy.TORRENT_PATH))
		self.opt_splash.SetValue(self.parent.pol(policy.CBT_SHOWSPLASH))
		
		lang = self.parent.pol(policy.CBT_LANG)
		
		if lang == "pl_PL":
			self.opt_lang.SetSelection(0)
		else:
			self.opt_lang.SetSelection(1)

		
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
		dl = wx.DirDialog(self, _('Choose directory'), '/', style = wx.DD_NEW_DIR_BUTTON )
		if dl.ShowModal() == wx.ID_OK:
			x = dl.GetPath()
			return x
