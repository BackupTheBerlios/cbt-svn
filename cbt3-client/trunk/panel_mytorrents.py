#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_mytorrents.py 75 2004-08-29 21:21:07Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys
from wxPython.xrc import *

from images import Images
from panel_maketorrent import PanelMakeTorrent

class PanelMyTorrents(wx.MDIChildFrame):
	def __init__(self, parent, id):
		wx.MDIChildFrame.__init__(self, parent, id, title=_("My torrents"), style = wx.DEFAULT_FRAME_STYLE)
		
		self.parent = parent
		
		self.images = Images(".")
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelMT")
		self.SetIcon(self.images.GetImage("icn_my"))

		self.Activate()
		
		self.Bind(wx.EVT_BUTTON, self.OnNewTorrent, id=XRCID("btnMyCreate"))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
	def OnNewTorrent(self, evt=None):
		win = PanelMakeTorrent(self.parent, -1, addtorrentfunc=self.AddCreatedTorrent)
		win.Show(True)
		
	def AddCreatedTorrent(self, rsp):
		self.parent.btq.do_add(rsp)
		self.parent.log.AddMsg('BTQueue', _('Added created torrent: %s') % rsp)
		
	def OnClose(self, evt):
		self.parent.windows["my"] = 0
		self.Destroy()
	
