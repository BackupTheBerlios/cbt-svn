#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_transfer_details.py 109 2004-08-31 01:12:37Z warp $
#-----------------------------------------------------------------------------

import wx, os, os.path, sys
from wxPython.xrc import *
from wxPython.html import *

from images import Images
from cbt_func import *

class PanelTransferDetails(wx.MDIChildFrame):
	def __init__(self, parent, id, btq=None, qid=None):
		wx.MDIChildFrame.__init__(self, parent, id, title="", size = (520,440), style = wx.DEFAULT_FRAME_STYLE)
		
		self.btq = btq
		self.qid = qid
		self.parent = parent

		self.images = Images(".")
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelTD")
		self.SetIcon(self.images.GetImage("icn_info"))
		
		self.listconn = XRCCTRL(self, "listconn")
		self.listconn.SetFont(defFontN)
		self.listfile = XRCCTRL(self, "listfiles")
		self.listfile.SetFont(defFontN)
		self.label = XRCCTRL(self, "label")
		self.htmlParts = XRCCTRL(self, "htmlParts")
		self.htmlStats = XRCCTRL(self, "htmlStats")
		self.htmlParts.SetBorders(2)
		self.htmlStats.SetBorders(2)
		self.tcount = 99

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_LEFT_DOWN, self.OnClose, id = XRCID("htmlStats"))

		self.Activate()
		
		# titles/labels
		
		list = self.btq.CbtList()
		for d in list:
			if d['id'] == qid:
				self.label.SetLabel(d['title'])
				self.SetTitle(d['title'])
		
		# columns
		
		cols = [ 
				 [0, _("IP / Nick"), wx.LIST_FORMAT_LEFT, 112],
				 [1, _("% done"), wx.LIST_FORMAT_LEFT, 55],
				 [2, _("Downloaded"), wx.LIST_FORMAT_LEFT, 55],
				 [3, _("Sent"), wx.LIST_FORMAT_LEFT, 55],
				 [4, _("UP Spd"), wx.LIST_FORMAT_LEFT, 52],
				 [5, _("DL Spd"), wx.LIST_FORMAT_LEFT, 52],
				 [6, _("Client"), wx.LIST_FORMAT_LEFT, 72],
				 [7, _("Netname"), wx.LIST_FORMAT_LEFT, 90],
			]
		
		InsertColumns(self.listconn, cols)
		
		cols = [
				[0, _("File"), wx.LIST_FORMAT_LEFT, 450],
				[1, _("Progress"), wx.LIST_FORMAT_LEFT, 70]
			]
		
		InsertColumns(self.listfile, cols)			

		# image list

		il = wx.ImageList(18, 12)
		il.Add(self.images.GetImage('blank'))

		self.flags = {}
		flags = self.images.GetImage('flags')
		for key, flag in flags.items():
			key = key.upper()
			self.flags[key] = il.Add(flag)

		self.listconn.AssignImageList(il, wx.IMAGE_LIST_SMALL)

		# timer

		self.UpdateLists()
		self.timer1 = wx.PyTimer(self.UpdateLists)
		self.timer1.Start(3500)
		
	def OnClose(self, evt):
		self.timer1.Stop()
		self.parent.tdwindows[self.qid] = 0
		self.Destroy()

	def UpdateLists(self):
		self.UpdateConnList()
		self.UpdatePiecesList()
		self.UpdateFileList()

	def UpdatePiecesList(self):
		data = self.btq.CbtDetail(self.qid)
		
		ftpl = file("tpl.html", "r")
		tpl = ftpl.read()
		ftpl.close()
		
		tpl = tpl.replace("{status}", data['btstatus'])
		tpl = tpl.replace("{seeds}", data['seeds'])
		tpl = tpl.replace("{peers}", data['peers'])
		tpl = tpl.replace("{copies}", '%(copies)0.4f'%data)
		tpl = tpl.replace("{dlsize}", data['dlsize'])
		tpl = tpl.replace("{ulsize}", data['ulsize'])
		tpl = tpl.replace("{dlspeed}", data['dlspeed'])
		tpl = tpl.replace("{ulspeed}", data['ulspeed'])
		tpl = tpl.replace("{ratio}", data['ratio'])
		tpl = tpl.replace("{eta}", data['eta'])
		tpl = tpl.replace("{filename}", os.path.basename(data['filename']))
		tpl = tpl.replace("{totalsize}", data['totalsize'])
		#~ tpl = tpl.replace("{dest_path}", data['dest_path'])
		tpl = tpl.replace("{infohash}", data['infohash'].strip())
		tpl = tpl.replace("{announce}", data['announce'])
		#~ tpl = tpl.replace("{peer_id}", data['peer_id'])
		tpl = tpl.replace("{totalsize}", data['totalsize'])
		
		if data['btstatus'] == "seedowany":
			self.SetTitle('[SEED] ' + data['title'])
		else:
			self.SetTitle('[' + data['progress'] + '] ' + data['title'])
		
		self.htmlStats.SetPage(tpl)

		# pieces
		
		self.tcount += 1
		
		if self.tcount > 5:

			self.tcount = 0
			
			try:
				
				cnt = ''
				stat = self.btq.CbtStat(self.qid)
				
				total = len(stat['piecescomplete'])
				pcs = {}
				it = 0
				
				for i in stat['numactive']:
					if i: 
						pcs[it] = 2
					else:
						pcs[it] = 0
					it += 1
			
				it = 0
				
				for i in stat['piecescomplete']:
					if i and not pcs[it]:
						cnt = cnt + '<img src="data/blk_1_100.png" width=10 height=11>'
					elif not i and not pcs[it]:
						cnt = cnt + '<img src="data/blk_0_100.png" width=10 height=11>'
					elif pcs[it]:
						cnt = cnt + '<img src="data/blk_2_100.png" width=10 height=11>'
					it += 1
			except:
				cnt = ''
					
			self.htmlParts.SetPage(cnt)
	
	def UpdateConnList(self):
		lst = self.listconn
		data = self.btq.CbtSpew(self.qid)
		
		rid = 0
		
		if lst.GetItemCount() <> len(data):
			lst.DeleteAllItems()
			for d in data:
				d['id'] = rid
				self.ConnListItem(lst, d, mode="add")
				rid += 1
		else:
			for d in data:
				d['id'] = rid
				self.ConnListItem(lst, d, id=int(d['id']), mode="update")
				rid += 1

	def ConnListItem(self, lst, d, id=None, mode=None):
		cc = d['cc']
		if self.flags.has_key(cc):
			ico = self.flags[cc]
			d['cc'] = ''
		else:
			ico = 0
			
		if mode=="add":
			item_idx = lst.GetItemCount()
			lst.InsertImageStringItem(item_idx, d['ip'], ico)
		elif mode=="update":
			item_idx = lst.FindItemData(-1, id)
			lst.SetStringItem(item_idx, 0, d['ip'], ico)

		#~ lst.SetStringItem(item_idx, 1, d['ip'])
		lst.SetStringItem(item_idx, 1, d['completed'])
		lst.SetStringItem(item_idx, 2, d['utotal'])
		lst.SetStringItem(item_idx, 3, d['dtotal'])
		lst.SetStringItem(item_idx, 4, d['uprate'])
		lst.SetStringItem(item_idx, 5, d['downrate'])
		lst.SetStringItem(item_idx, 6, d['client'][:12])
		lst.SetStringItem(item_idx, 7, d['netname'])
		#~ lst.SetStringItem(item_idx, 9, d['msg'])

		tid = int(d['id'])
		lst.SetItemData(item_idx, tid)

	def UpdateFileList(self):
		
		pass
