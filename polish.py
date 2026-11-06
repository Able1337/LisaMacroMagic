"""Small reusable UI pieces, with no access to macros or input hooks."""
from PySide6.QtCore import Qt,QUrl
from PySide6.QtGui import QPainter,QColor,QDesktopServices
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QAbstractSpinBox,QDialog,QVBoxLayout,QLabel,QFrame


class Stepper(QWidget):
    def __init__(self,spin,parent=None):
        super().__init__(parent)
        self.setObjectName('stepper')
        layout=QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        self.minus=QPushButton('−'); self.plus=QPushButton('+'); self.spin=spin
        for button,description in [(self.minus,'Уменьшить на секунду'),(self.plus,'Увеличить на секунду')]:
            button.setObjectName('stepperButton'); button.setFixedSize(30,36)
            button.setCursor(Qt.CursorShape.PointingHandCursor); button.setToolTip(description)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter); spin.setFixedSize(46,36)
        spin.setAccessibleName('Задержка в секундах')
        self.minus.clicked.connect(spin.stepDown); self.plus.clicked.connect(spin.stepUp)
        for widget in (self.minus,spin,self.plus): layout.addWidget(widget)
        spin.valueChanged.connect(self.refresh); self.refresh()

    def refresh(self,*args):
        self.minus.setEnabled(self.spin.value()>self.spin.minimum())
        self.plus.setEnabled(self.spin.value()<self.spin.maximum())


class JapanFlag(QWidget):
    """Windows renders regional-indicator flags as letters; draw the flag locally."""
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(60,40)
        self.setAccessibleName('🇯🇵'); self.setToolTip('Япония')

    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor('#ffffff'))
        painter.drawRoundedRect(self.rect(),4,4)
        painter.setBrush(QColor('#bc002d')); painter.drawEllipse(18,8,24,24)


class DateIdeaDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('dateDialog'); self.setWindowTitle('a little secret ♡')
        self.setFixedSize(440,330)
        layout=QVBoxLayout(self); layout.setContentsMargins(28,24,28,24); layout.setSpacing(14)
        label=QLabel('you found a little secret'); label.setObjectName('muted'); label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(label)
        self.setAccessibleDescription('👫 🇯🇵 — date idea?')
        emoji_row=QHBoxLayout(); emoji_row.setSpacing(18); emoji_row.addStretch()
        self.emojis=QLabel('👫'); self.emojis.setObjectName('dateEmojis'); self.emojis.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emoji_row.addWidget(self.emojis); self.flag=JapanFlag(); emoji_row.addWidget(self.flag); emoji_row.addStretch(); layout.addLayout(emoji_row)
        self.title=QLabel('date idea?'); self.title.setObjectName('dateTitle'); self.title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.title)
        caption=QLabel('Рамен на двоих, прогулка по Токио\nи немного магии под сакурой 🌸')
        caption.setWordWrap(True); caption.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(caption)
        self.telegram=QPushButton('Telegram · @Able_ebg')
        self.telegram.setCursor(Qt.CursorShape.PointingHandCursor)
        self.telegram.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://t.me/Able_ebg')))
        layout.addWidget(self.telegram,alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        close=QPushButton('♡ sounds like a plan'); close.setObjectName('primary'); close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept); layout.addWidget(close)
