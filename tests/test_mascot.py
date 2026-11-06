import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QMovie,QImageReader
import mascot


class MascotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def test_all_animation_frames_have_transparent_background_and_keep_fox_pixels(self):
        movie=QMovie(str(mascot.asset('fox.gif')))
        self.assertTrue(movie.isValid()); self.assertEqual(movie.frameCount(),14)
        unique=set()
        for frame in range(movie.frameCount()):
            self.assertTrue(movie.jumpToFrame(frame))
            original=movie.currentImage().copy(85,0,85,85)
            tile=mascot.transparent_tile(movie.currentImage())
            transparent=0; opaque=0
            for y in range(85):
                for x in range(85):
                    color=original.pixel(x,y)
                    if color in (0xff181818,0xff313131,0xff393439):
                        self.assertEqual(tile.pixelColor(x,y).alpha(),0); transparent+=1
                    else:
                        self.assertEqual(tile.pixel(x,y),color); opaque+=1
            self.assertGreater(transparent,2000); self.assertGreater(opaque,2000)
            unique.add(bytes(tile.constBits()))
        self.assertGreater(len(unique),1)

    def test_executable_icon_has_alpha(self):
        image=QImageReader(str(mascot.asset('fox.ico'))).read()
        self.assertFalse(image.isNull()); self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0,0).alpha(),0)
        self.assertTrue(any(image.pixelColor(x,y).alpha()==255 for x in range(image.width()) for y in range(image.height())))
