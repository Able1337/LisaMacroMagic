"""Local Qt input test surface; no global hooks, no files, no network."""
import sys
from datetime import datetime
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QPlainTextEdit

STYLE='''
    QWidget { background:#241c2c; color:#f4e2f0; }
    QLabel#title { font-size:25px; font-weight:700; color:#f4a4d2; }
    QLabel#surface { background:#403047; border:2px dashed #b87aaf; border-radius:18px; padding:26px; font-size:19px; }
    QPlainTextEdit { background:#19141f; border:1px solid #62456a; border-radius:10px; padding:8px; color:#eedaf0; }
    QPushButton { background:#583b60; border:1px solid #916398; border-radius:9px; padding:9px 16px; }
    QPushButton:hover { background:#754e7d; }
'''


def modifiers(event):
    value=event.modifiers()
    return [label for flag,label in [(Qt.KeyboardModifier.ControlModifier,'Ctrl'),
        (Qt.KeyboardModifier.AltModifier,'Alt'),(Qt.KeyboardModifier.ShiftModifier,'Shift'),
        (Qt.KeyboardModifier.MetaModifier,'Win')] if value & flag]


def key_name(event):
    key=event.key()
    names={Qt.Key.Key_Control:'Ctrl',Qt.Key.Key_Alt:'Alt',Qt.Key.Key_Shift:'Shift',Qt.Key.Key_Meta:'Win',
        Qt.Key.Key_Return:'Enter',Qt.Key.Key_Enter:'Num Enter',Qt.Key.Key_Space:'Space',Qt.Key.Key_Tab:'Tab',
        Qt.Key.Key_Backtab:'Tab',Qt.Key.Key_Escape:'Esc',Qt.Key.Key_Backspace:'Backspace',Qt.Key.Key_Delete:'Delete',
        Qt.Key.Key_Insert:'Insert',Qt.Key.Key_Home:'Home',Qt.Key.Key_End:'End',Qt.Key.Key_PageUp:'PageUp',
        Qt.Key.Key_PageDown:'PageDown',Qt.Key.Key_Left:'Left',Qt.Key.Key_Right:'Right',Qt.Key.Key_Up:'Up',Qt.Key.Key_Down:'Down'}
    if key in names: return names[key]
    if Qt.Key.Key_F1<=key<=Qt.Key.Key_F35: return f'F{key-Qt.Key.Key_F1+1}'
    if 32<=key<0x110000: return chr(key)
    return f'QtKey {key}'


class Monitor(QWidget):
    def __init__(self,parent=None,theme='dark'):
        super().__init__(parent,Qt.WindowType.Window)
        self.setWindowTitle('Lisa Input Monitor — клавиши, сочетания и мышь')
        self.resize(1000,730)
        self.setFont(QFont('Segoe UI',11))
        self.set_theme(theme)
        layout=QVBoxLayout(self); layout.setContentsMargins(22,20,22,20); layout.setSpacing(12)
        title=QLabel('🎀 Lisa Input Monitor'); title.setObjectName('title'); layout.addWidget(title)
        explanation=QLabel('Кликни в поле ниже и запускай макрос. Журнал показывает события только этого окна.\n'
            'Стрелки ↓ / ↑ — нажатие / отпускание. Бинды запуска и управляющая клавиша перехватываются приложением и в журнал не попадают.'); explanation.setWordWrap(True); layout.addWidget(explanation)
        self.surface=QLabel('🖱  Поле проверки\nЛКМ · ПКМ · колёсико · клавиши · Ctrl+Shift+S')
        self.surface.setObjectName('surface'); self.surface.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.surface.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.surface.setMinimumHeight(140)
        self.surface.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu); layout.addWidget(self.surface)
        self.last=QLabel('Последнее событие: ожидание…'); self.last.setWordWrap(True); layout.addWidget(self.last)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(5000)
        self.log.setFont(QFont('Consolas',11)); self.log.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu); layout.addWidget(self.log,1)
        row=QHBoxLayout(); self.clear=QPushButton('Очистить журнал'); self.clear.clicked.connect(self.clear_log); row.addWidget(self.clear)
        self.copy=QPushButton('Скопировать журнал'); self.copy.clicked.connect(self.copy_log); row.addWidget(self.copy)
        row.addStretch(); self.count=QLabel('Событий: 0'); row.addWidget(self.count); layout.addLayout(row)
        self.sequence=0
        self.filter_active=False
        self.surface.setFocus()

    def set_theme(self,theme):
        style=STYLE
        if theme=='pink':
            for dark,pink in {'#241c2c':'#fff0f7','#f4e2f0':'#684366','#f4a4d2':'#ac427d',
                '#403047':'#f5e3f1','#b87aaf':'#bb80b2','#19141f':'#fffafd','#62456a':'#e3cce1',
                '#eedaf0':'#684366','#583b60':'#f9e5f1','#916398':'#eacbdf','#754e7d':'#f2cde5'}.items():
                style=style.replace(dark,pink)
        self.setStyleSheet(style)

    def showEvent(self,event):
        if not self.filter_active:
            QApplication.instance().installEventFilter(self); self.filter_active=True
        super().showEvent(event)

    def closeEvent(self,event):
        if self.filter_active:
            QApplication.instance().removeEventFilter(self); self.filter_active=False
        super().closeEvent(event)

    def copy_log(self): QApplication.clipboard().setText(self.log.toPlainText())

    def clear_log(self):
        self.log.clear(); self.sequence=0; self.count.setText('Событий: 0'); self.last.setText('Журнал очищен'); self.surface.setFocus()

    def add(self,text):
        self.sequence+=1
        stamp=datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.log.appendPlainText(f'{self.sequence:04d}  {stamp}  {text}')
        self.last.setText(text); self.count.setText(f'Событий: {self.sequence}')

    def eventFilter(self,obj,event):
        if not self.isVisible() or not isinstance(obj,QWidget) or obj.window() is not self: return False
        kind=event.type()
        if kind==QEvent.Type.ShortcutOverride:
            event.accept(); return True
        if kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
            name=key_name(event); mods=modifiers(event)
            combination='+'.join(mods+([] if name in mods else [name]))
            direction='↓ НАЖАТО' if kind==QEvent.Type.KeyPress else '↑ ОТПУЩЕНО'
            text=event.text()
            suffix=f' · текст={text!r}' if text else ''
            repeat=' · автоповтор' if event.isAutoRepeat() else ''
            keypad=' · NumPad' if event.modifiers() & Qt.KeyboardModifier.KeypadModifier else ''
            self.add(f'⌨ {direction}: {combination} · VK={event.nativeVirtualKey()} · scan={event.nativeScanCode()}{keypad}{repeat}{suffix}')
            event.accept(); return True
        if kind in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease,QEvent.Type.MouseButtonDblClick):
            names={Qt.MouseButton.LeftButton:'ЛКМ',Qt.MouseButton.RightButton:'ПКМ',Qt.MouseButton.MiddleButton:'СКМ',
                   Qt.MouseButton.BackButton:'Назад (X1)',Qt.MouseButton.ForwardButton:'Вперёд (X2)'}
            button=names.get(event.button(),str(event.button()))
            action={QEvent.Type.MouseButtonPress:'↓ НАЖАТО',QEvent.Type.MouseButtonRelease:'↑ ОТПУЩЕНО',QEvent.Type.MouseButtonDblClick:'ДВОЙНОЙ КЛИК'}[kind]
            point=event.globalPosition(); local=self.mapFromGlobal(point.toPoint())
            prefix='+'.join(modifiers(event))
            self.add(f'🖱 {action}: {prefix+"+" if prefix else ""}{button} · экран=({int(point.x())}, {int(point.y())}) · окно=({local.x()}, {local.y()})')
            if obj is self.surface:
                self.surface.setFocus(); event.accept(); return True
        if kind==QEvent.Type.Wheel:
            delta=event.angleDelta(); prefix='+'.join(modifiers(event))
            self.add(f'↕ ПРОКРУТКА: X={delta.x()}, Y={delta.y()} (1 шаг = 120)'+(f' · {prefix}' if prefix else ''))
            event.accept(); return True
        if kind==QEvent.Type.WindowDeactivate and obj is self:
            self.add('○ Окно потеряло фокус; события других приложений не отслеживаются')
        return False


if __name__=='__main__':
    app=QApplication(sys.argv); window=Monitor(); window.show(); sys.exit(app.exec())
