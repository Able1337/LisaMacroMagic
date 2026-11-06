"""Render the user's animated atlas with its checkerboard and dither colors keyed out."""
import sys
from pathlib import Path
from PySide6.QtCore import QRectF,Qt,Signal
from PySide6.QtGui import QMovie,QPainter,QIcon,QImage
from PySide6.QtWidgets import QWidget


def asset(name):
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/name


def icon(): return QIcon(str(asset('fox.ico')))


def transparent_tile(image):
    """A render-time color key; original GIF and pixel artwork stay intact."""
    tile=image.copy(85,0,85,85).convertToFormat(QImage.Format.Format_ARGB32)
    # Exact colors of the baked-in checkerboard, distinct from fox outline colors.
    background={0xff181818,0xff313131,0xff393439}
    for y in range(tile.height()):
        for x in range(tile.width()):
            if tile.pixel(x,y) in background: tile.setPixel(x,y,0)
    return tile


class Fox(QWidget):
    clicked=Signal()
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(64,64)
        self.setToolTip('Лисичка знает маленький секрет ♡')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.movie=QMovie(str(asset('fox.gif')))
        self.frames={}
        self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self.movie.frameChanged.connect(lambda _:self.update())
        self.movie.start()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,False)
        index=self.movie.currentFrameNumber()
        image=self.movie.currentImage()
        if image.isNull(): return
        if index not in self.frames: self.frames[index]=transparent_tile(image)
        painter.drawImage(QRectF(self.rect()),self.frames[index])

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(); event.accept(); return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self,event):
        event.accept()
