#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_transfers.py 109 2004-08-31 01:12:37Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys
from wxPython.xrc import *

from images import Images
from cbt_func import *

class PanelTransfers(wx.MDIChildFrame):
	def __init__(self, parent, id, btq=None):
		wx.MDIChildFrame.__init__(self, parent, id, size = (560,340), title=_("Transfers"), style = wx.DEFAULT_FRAME_STYLE)
		
		self.btq = btq
		self.parent = parent
		
		self.images = Images(".")
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelDL")
		self.SetIcon(self.images.GetImage("icn_down"))
		
		self.list = XRCCTRL(self, "listDL")
		self.url = XRCCTRL(self, "textDLURL")
		#~ self.list.SetWindowStyleFlag(wx.LC_REPORT | wx.LC_VRULES | wx.LC_SINGLE_SEL | wx.FIXED_MINSIZE )
		self.list.SetFont(defFontN)
		
		self.il = wx.ImageList(16, 16)
		self.il.Add(self.images.GetImage("l_play"))
		self.il.Add(self.images.GetImage("l_pause"))
		self.il.Add(self.images.GetImage("l_seed"))
		self.il.Add(self.images.GetImage("l_queue"))
		self.il.Add(self.images.GetImage("l_finished"))
		
		self.list.AssignImageList(self.il, wx.IMAGE_LIST_SMALL)

		self.Activate()
		
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_BUTTON, self.OnAddUrl, id=XRCID("btnDLAddURL"))
		
		self.Bind(wx.EVT_BUTTON, self.OnQueueResume, id=XRCID("btnDlResume"))
		self.Bind(wx.EVT_BUTTON, self.OnQueuePause, id=XRCID("btnDlPause"))
		self.Bind(wx.EVT_BUTTON, self.OnQueueRemove, id=XRCID("btnDlRemove"))
		self.Bind(wx.EVT_BUTTON, self.OnDisplayDetails, id=XRCID("btnDlDetails"))
		
		self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnDisplayDetails, id=XRCID("listDL"))
		
		# gettext
		
		XRCCTRL(self, "btnDlResume").SetToolTip( wx.ToolTip( _("Resume") ) )
		XRCCTRL(self, "btnDlPause").SetToolTip( wx.ToolTip( _("Pause") ) )
		XRCCTRL(self, "btnDlRemove").SetToolTip( wx.ToolTip( _("Remove") ) )
		XRCCTRL(self, "btnDlDetails").SetToolTip( wx.ToolTip( _("Details") ) )
		
		XRCCTRL(self, "btnDLAddURL").SetLabel( _("Add URL") )
				
		# cols
		
		cols = [ [0, _("Title"), wx.LIST_FORMAT_LEFT, 200],
				 [1, _("State"), wx.LIST_FORMAT_LEFT, 80],
				 [2, _("Progress"), wx.LIST_FORMAT_LEFT, 80],
				 [3, _("ETA"), wx.LIST_FORMAT_LEFT, 80],
				 [4, _("DL Spd"), wx.LIST_FORMAT_LEFT, 60],
				 [5, _("UP Spd"), wx.LIST_FORMAT_LEFT, 60],
				 [6, _("Seeds"), wx.LIST_FORMAT_LEFT, 48],
				 [7, _("Peers"), wx.LIST_FORMAT_LEFT, 48],
				 [8, _("Ratio"), wx.LIST_FORMAT_LEFT, 50],
				 [9, _("Last message"), wx.LIST_FORMAT_LEFT, 100]
				 ]
				 
		InsertColumns(self.list, cols)
		
		# timers
		
		self.UpdateList()
		self.timer1 = wx.PyTimer(self.UpdateList)
		self.timer1.Start(1500)
		
	def OnDisplayDetails(self, evt):
		id = self.list.GetFirstSelected()
		
		if id > -1:
			qid = str ( self.list.GetItemData(id) )
			self.parent.OnTransferDisplayDetails(qid=qid)
		
	def OnQueueResume(self, evt):
		id = self.list.GetFirstSelected()
		
		if id > -1:
			qid = str ( self.list.GetItemData(id) )
			self.btq.do_resume(qid)
			self.parent.log.AddMsg("BTQueue", _("Resumed: %s") % qid)
			
	def OnQueuePause(self, evt):
		id = self.list.GetFirstSelected()
		
		if id > -1:
			qid = str ( self.list.GetItemData(id) )
			self.btq.do_pause(qid)
			self.parent.log.AddMsg("BTQueue", _("Paused: %s") % qid)
		
	def OnQueueRemove(self, evt):
		id = self.list.GetFirstSelected()
		
		if id > -1:
			qid = str ( self.list.GetItemData(id) )
			self.btq.do_remove(qid)
			self.parent.log.AddMsg("BTQueue", _("Removed: %s") % qid)
		
	def OnAddUrl(self, evt):
		url = self.url.GetValue()
		if url:
			status = self.btq.do_add(url)
			print status
			self.parent.log.AddMsg("BTQueue", _("Added URL: %s") % url)
			self.url.SetValue('')
		
	def OnClose(self, evt):
		self.timer1.Stop()
		self.parent.windows["transfers"] = 0
		self.Destroy()
		
	def UpdateList(self):
		try:
			lst = self.list
			data = self.btq.CbtList()
			
			if lst.GetItemCount() <> len(data):
				lst.DeleteAllItems()
				for d in data:
					self.ListItem(lst, d, mode="add")
			else:
				for d in data:
					self.ListItem(lst, d, id=int(d['id']), mode="update")
		except Exception, e:
			print str(e)
			pass

	def ListItem(self, lst, d, id=None, mode=None):
		
		if d['btstatus'] == _('paused'):
			icon = 1
		elif d['btstatus'] == _('finished'):
			icon = 4
		elif d['btstatus'] == _('seeding'):
			icon = 2
		elif d['btstatus'] == _('running'):
			icon = 0
		elif d['btstatus'] == _('waiting'):
			icon = 3
		
		if mode=="add":
			item_idx = lst.GetItemCount()
			lst.InsertImageStringItem(item_idx, d['title'], icon)
		elif mode=="update":
			item_idx = lst.FindItemData(-1, id)
			lst.SetStringItem(item_idx, 0, d['title'], icon)
		
		lst.SetStringItem(item_idx, 1, d['btstatus'])
		lst.SetStringItem(item_idx, 2, d['progress'])
		lst.SetStringItem(item_idx, 3, d['eta'])
		lst.SetStringItem(item_idx, 4, d['dlspeed'])
		lst.SetStringItem(item_idx, 5, d['ulspeed'])
		lst.SetStringItem(item_idx, 6, d['seeds'])
		lst.SetStringItem(item_idx, 7, d['peers'])
		lst.SetStringItem(item_idx, 8, d['ratio'])
		lst.SetStringItem(item_idx, 9, d['msg'])

		tid = int(d['id'])
		lst.SetItemData(item_idx, tid)
