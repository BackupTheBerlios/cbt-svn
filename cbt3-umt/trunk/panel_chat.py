# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_chat.py 93 2004-08-30 17:15:39Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys
from wxPython.xrc import *

from images import Images

class PanelChat(wx.MDIChildFrame):
	def __init__(self, parent, id):
		wx.MDIChildFrame.__init__(self, parent, id, title="Chat", style = wx.DEFAULT_FRAME_STYLE)
		
		self.parent = parent
		self.images = Images(".")
		#~ self.xrc = wxXmlResource('panels.xrc')
		#~ self.xrc.LoadPanel(self, "panelMT")
		self.SetIcon(self.images.GetImage("icn_chat"))

		self.Activate()
		
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_SET_FOCUS, self.OnActivate)

	def OnClose(self, evt):
		self.parent.windows["chat"] = 0
		self.Destroy()

	def OnActivate(self, evt):
		self.images = Images(".")
		self.SetIcon(self.images.GetImage("icn_chat"))
