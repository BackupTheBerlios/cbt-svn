del ../../cbt3-bin/*.exe
del ../../cbt3-bin/*.pyd
del ../../cbt3-bin/*.dll
winsetup.py py2exe
upx -9 ../../cbt3-bin/trunk/*.*

