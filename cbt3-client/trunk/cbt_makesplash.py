from cbt_vars import *
from BitQueue import version as btqver
from time import *
import Image, ImageFont, ImageDraw

fn11 = ImageFont.truetype("framd.ttf",13)
#~ font = ImageFont.load_default()

xb = 163
yb = 191
spac = 13

t = localtime(time())
timestamp = "%s" % (strftime("%Y.%m.%d %H:%M:%S", t))

image = Image.open('_gui/splash.png')

draw = ImageDraw.Draw(image)
#~ draw.text((xb, yb), prog_name_long, font=fb11)
draw.text((xb, yb+(spac*1)), "wersja "+prog_ver+" build " +prog_build, font=fn11)
draw.text((xb, yb+(spac*2)), "datecode "+str(timestamp), font=fn11)
draw.text((xb, yb+(spac*4)), "engine: "+btqver, font=fn11)

draw.text((xb, yb+(spac*6)), "warp // visualvinyl.net 2004", font=fn11)

image.save('data/splash.png')
