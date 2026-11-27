"""Lisa's Macro Magic — user-configured local macro studio."""
import copy
import ctypes
import json
import sys
import threading
from pathlib import Path
import storage
from mascot import Fox,icon
from polish import Stepper,DateIdeaDialog
from affirmations import AffirmationCard,TIME_HINT

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QElapsedTimer, QUrl
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QLineEdit, QCheckBox, QSplitter, QFrame,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox,
    QMessageBox, QFileDialog, QAbstractItemView, QMenu, QSystemTrayIcon)
import model
from engine import Player, Recorder, foreground
from updates import UpdateCheck, RELEASE_URL
import update_install

VERSION = '0.5.18'
WINDOW_TITLE = f"Lisa's Macro Magic 🎀 — v{VERSION}"
STYLE = """
QMainWindow, QDialog { background:#fff0f7; color:#684366; }
QWidget { font-family:'Segoe UI'; font-size:14px; color:#684366; }
QWidget#root { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #fff0f7,stop:1 #eee4ff); }
QFrame#card { background:#fffafd; border:1px solid white; border-radius:22px; }
QLabel#title { color:#ac427d; font-size:28px; font-weight:700; }
QLabel#muted { color:#947790; font-size:12px; }
QLabel#status { background:#f1e6fc; border-radius:12px; padding:12px; color:#79549a; }
QPushButton { background:#f9e5f1; border:1px solid #eacbdf; border-radius:11px; padding:9px 13px; font-weight:600; }
QPushButton:hover { background:#f2cde5; border-color:#bb80b2; }
QPushButton:pressed { background:#e9bfdc; }
QPushButton:disabled { color:#bca9b7; background:#f4edf2; border-color:#e8dfe5; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ec91bf,stop:1 #c69be3); color:white; border:0; }
QPushButton#stop { background:#ffe3ed; color:#b23c68; border-color:#e7a4bd; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:white; border:1px solid #e3cce1; border-radius:9px; padding:7px; }
QListWidget { background:#fffafd; border:1px solid #eddaea; border-radius:12px; padding:5px; outline:0; }
QListWidget::item { padding:12px 9px; border-radius:8px; margin:2px; }
QListWidget::item:selected { background:#f0d7ec; color:#82416f; }
QListWidget::item:hover { background:#f8eaf4; }
QListWidget#steps::item { padding:8px 9px; margin:1px; }
QCheckBox { spacing:8px; }
QSplitter::handle { background:transparent; width:12px; }
QPushButton:focus,QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border:1px solid #bb80b2; }
QPushButton#primary:hover { background:#c882bc; }
QPushButton#primary:pressed { background:#b373ae; }
QPushButton#primary:disabled { background:#e8dfe5; color:#bca9b7; }
QPushButton#stop:hover { background:#f2cde5; }
QFrame#settingsCard { background:#fffafd; border:1px solid #eddaea; border-radius:14px; }
QPushButton#stepperButton { padding:0; border-radius:8px; font-size:18px; }
QWidget#stepper QSpinBox { border:0; background:transparent; padding:0; }
QWidget#stepper QSpinBox:focus { background:#f0d7ec; border-radius:7px; }
QLabel#section { font-size:15px; font-weight:600; color:#ac427d; padding-bottom:5px; }
QLabel#dateEmojis { font-size:42px; background:transparent; }
QLabel#dateTitle { font-size:32px; font-weight:700; color:#ac427d; }
QListWidget::item:disabled { color:#bca9b7; }
QScrollBar:vertical { background:transparent; width:8px; margin:4px 0; }
QScrollBar::handle:vertical { background:#e3cce1; border-radius:4px; min-height:24px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QToolTip { background:#fffafd; color:#684366; border:1px solid #e3cce1; padding:6px; }
QComboBox QAbstractItemView { background:#fffafd; color:#684366; border:1px solid #e3cce1; selection-background-color:#f0d7ec; }
QFrame#affirmationCard { background:#f1e6fc; border:0; border-radius:15px; }
QLabel#affirmationCaption { color:#947790; font-size:10px; font-weight:600; background:transparent; }
QLabel#affirmationText { color:#79549a; font-size:13px; background:transparent; }
"""
DARK_STYLE=STYLE
for light,dark in {'#fff0f7':'#211b29','#fffafd':'#2b2234','#eee4ff':'#32263e',
    '#684366':'#f1ddeb','#ac427d':'#f5aad7','#947790':'#baa5bc','#f1e6fc':'#3b2c49',
    '#79549a':'#e0c2f4','#f9e5f1':'#44304b','#eacbdf':'#68466d','#f2cde5':'#5a3b61',
    '#bb80b2':'#bf86bd','#e9bfdc':'#694773','#bca9b7':'#817187','#f4edf2':'#302936',
    '#e8dfe5':'#47374f','#ffe3ed':'#542c40','#b23c68':'#ffadc8','#e7a4bd':'#96506c',
    '#e3cce1':'#68466d','#eddaea':'#5a3f64','#f0d7ec':'#63436b','#82416f':'#ffe3f8',
    '#f8eaf4':'#46314f','solid white':'solid #49344f','background:white':'background:#34283d'}.items():
    DARK_STYLE=DARK_STYLE.replace(light,dark)
DARK_STYLE+='QToolTip,QMenu { background:#34283d; color:#f1ddeb; border:1px solid #68466d; }'


class Bridge(QObject):
    status = Signal(str, str)
    finished = Signal(str, str)
    record_stop = Signal(str)
    action = Signal(str)


class StepDialog(QDialog):
    TYPES = [('keys','⌨ Клавиша / сочетание'), ('delay','⏱ Пауза'), ('wait_click','♡ Ждать ручной ЛКМ'), ('wait_key','♡ Ждать нажатия клавиши'),
             ('click','🖱 Клик по координатам'), ('click_here','🖱 Клик под курсором'),
             ('repeat','↻ Повторить предыдущее действие'), ('call','▶ Выполнить сценарий'),
             ('move','↗ Перемещение мыши'), ('scroll','↕ Прокрутка'),
             ('key_down','Клавиша вниз (запись)'), ('key_up','Клавиша вверх (запись)'),
             ('mouse_down','Кнопка мыши вниз (запись)'), ('mouse_up','Кнопка мыши вверх (запись)')]

    def __init__(self, step=None, parent=None, call_targets=()):
        super().__init__(parent)
        self.setWindowTitle('Маленький шаг магии 🎀')
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for key, title in self.TYPES: self.kind.addItem(title,key)
        self.value = QLineEdit('ctrl+shift+s')
        self.seconds = QDoubleSpinBox(); self.seconds.setRange(.01,600); self.seconds.setDecimals(3); self.seconds.setValue(1)
        self.x, self.y = QSpinBox(), QSpinBox()
        for field in (self.x,self.y): field.setRange(-100000,100000)
        self.button = QComboBox(); self.button.addItems(['left','right','middle'])
        self.dx, self.dy = QSpinBox(), QSpinBox()
        for field in (self.dx,self.dy): field.setRange(-100,100)
        self.dy.setValue(-1)
        self.called_scenario = QComboBox()
        self.called_scenario.setPlaceholderText('Выбери сценарий')
        for scenario_id, title in call_targets:
            self.called_scenario.addItem(title,scenario_id)
        self.called_scenario.setCurrentIndex(-1)
        form.addRow('Тип шага',self.kind)
        self.fields = [('Клавиши', self.value),('Секунды / таймаут',self.seconds),('X экрана',self.x),('Y экрана',self.y),
                       ('Кнопка',self.button),('Прокрутка X',self.dx),('Прокрутка Y',self.dy),('Сценарий',self.called_scenario)]
        for label, field in self.fields: form.addRow(label,field)
        layout.addLayout(form)
        self.hint = QLabel()
        self.hint.setWordWrap(True); self.hint.setObjectName('muted'); layout.addWidget(self.hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_checked); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.form = form
        self.kind.currentIndexChanged.connect(self.update_fields)
        self.kind.currentIndexChanged.connect(self.wait_key_defaults)
        if step:
            self.kind.setCurrentIndex(self.kind.findData(step['type']))
            self.value.setText(step.get('value',''))
            self.seconds.setValue(step.get('seconds',1))
            for name in ('x','y','dx','dy'): getattr(self,name).setValue(step.get(name,0))
            self.button.setCurrentText(step.get('button','left'))
            if step['type']=='call':
                self.called_scenario.setCurrentIndex(self.called_scenario.findData(step['scenario_id']))
        self.update_fields()

    def update_fields(self):
        kind = self.kind.currentData()
        visible = {
            'keys':{0}, 'key_down':{0}, 'key_up':{0}, 'delay':{1}, 'wait_click':{1}, 'wait_key':{0,1},
            'move':{2,3}, 'click':{2,3,4}, 'click_here':{4}, 'repeat':set(), 'call':{7},
            'mouse_down':{2,3,4}, 'mouse_up':{2,3,4}, 'scroll':{5,6}}
        for i, (_,field) in enumerate(self.fields):
            field.setVisible(i in visible[kind]); self.form.labelForField(field).setVisible(i in visible[kind])
        self.hint.setText({
            'repeat':'Повторяет последнее действие в этом сценарии, в том числе ручной ЛКМ. Можно добавить после паузы.',
            'click_here':'Нажимает выбранную кнопку там, где находится курсор в момент выполнения.',
            'call':('Основной сценарий продолжится после завершения выбранного.' if self.called_scenario.count()
                    else 'Сначала создай ещё один сценарий в этом проекте.'),
        }.get(kind,'Клавиши: z, enter, ctrl+shift+s. space = пробел.\nБуквы обозначают клавиши S/Ы, Z/Я и т. п., а не ввод текста.\nОжидание клавиши или ЛКМ продолжается после нажатия и отпускания.\nНажатие проходит в браузер. Координаты — пиксели экрана.'))

    def wait_key_defaults(self):
        if self.kind.currentData()=='wait_key': self.value.setText('space'); self.seconds.setValue(120)

    def result_step(self):
        kind = self.kind.currentData(); result = {'type':kind}
        if kind in ('keys','key_down','key_up','wait_key'): result['value'] = self.value.text().strip().lower()
        if kind in ('delay','wait_click','wait_key'): result['seconds'] = self.seconds.value()
        if kind in ('click','move','mouse_down','mouse_up'): result.update(x=self.x.value(),y=self.y.value())
        if kind in ('click','click_here','mouse_down','mouse_up'): result['button'] = self.button.currentText()
        if kind == 'scroll': result.update(dx=self.dx.value(),dy=self.dy.value())
        if kind == 'call': result['scenario_id'] = self.called_scenario.currentData()
        return model.validate_step(result)

    def accept_checked(self):
        try: self.result_step()
        except ValueError as exc: QMessageBox.warning(self,'Проверь шаг',str(exc)); return
        self.accept()


class Window(QMainWindow):
    def __init__(self, native=True, persistence_path=None):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1150,850); self.setMinimumSize(1050,760)
        self.setWindowIcon(icon())
        self.setStyleSheet(STYLE)
        self.scenarios = [model.scenario('Мой первый сценарий','F6')]
        self.scenarios[0]['steps'] = [{'type':'keys','value':'z'}, {'type':'wait_click','seconds':120},
                                      {'type':'keys','value':'enter'}, {'type':'keys','value':'ctrl+shift+s'}]
        self.settings=dict(model.DEFAULT_SETTINGS)
        self.current = None; self.dirty = False
        self.path=Path(persistence_path) if persistence_path is not None else storage.default_path()
        self.autosave_blocked=False; self.load_error=None
        if self.path.exists():
            try:
                project=model.load_project(self.path)
                self.scenarios=project['scenarios']; self.settings=project['settings']
            except (OSError,ValueError,TypeError,RecursionError) as exc:
                self.autosave_blocked=True; self.load_error=str(exc)
        self.playbacks = {}
        self.input_lock = threading.Lock()
        self.playback_lock = threading.Lock()
        self.stopping_playback = False
        self.recorder = None; self.pending_record = 0
        self.record_target = None; self.close_pending = False; self.hotkeys = None; self.emergency = None
        self.tray=None; self.exit_requested=False
        self.input_monitor=None
        self.date_dialog=None; self.secret_clicks=0; self.secret_timer=QElapsedTimer()
        self.bridge = Bridge()
        self.bridge.status.connect(self.play_status)
        self.bridge.finished.connect(self.play_finished)
        self.bridge.record_stop.connect(self.finish_record)
        self.bridge.action.connect(self.handle_action)
        self.auto_timer=QTimer(self); self.auto_timer.setSingleShot(True); self.auto_timer.setInterval(700)
        self.auto_timer.timeout.connect(self.autosave)
        root = QWidget(); root.setObjectName('root'); self.setCentralWidget(root)
        outer = QVBoxLayout(root); outer.setContentsMargins(24,18,24,16); outer.setSpacing(12)
        header = QHBoxLayout(); self.fox=Fox(); header.addWidget(self.fox)
        header.setSpacing(14); self.fox.clicked.connect(self.fox_clicked)
        title = QLabel("Lisa's Macro Magic 🎀"); title.setObjectName('title'); header.addWidget(title); header.addStretch()
        self.affirmation=AffirmationCard(); header.addWidget(self.affirmation); outer.addLayout(header)
        subtitle_row=QHBoxLayout()
        subtitle = QLabel('Твои сценарии. Твои бинды. Немножко магии ♡'); subtitle.setObjectName('muted'); subtitle_row.addWidget(subtitle); subtitle_row.addStretch()
        version = QLabel(f'PINK EDITION  /  {VERSION}'); version.setObjectName('muted'); subtitle_row.addWidget(version); outer.addLayout(subtitle_row)
        toolbar = QHBoxLayout()
        self.open_btn = self.button('Открыть JSON',self.open_file,toolbar)
        self.save_btn = self.button('Сохранить',self.save_file,toolbar)
        self.save_as_btn = self.button('Сохранить как…',lambda:self.save_file(True),toolbar)
        self.release=None; self.update_stage=None; self.downloading=False; self.startup_check=False
        self.update_checker=UpdateCheck(VERSION,self)
        self.update_checker.finished.connect(self.update_finished)
        self.update_checker.downloaded.connect(self.update_downloaded)
        self.update_checker.progress.connect(self.update_progress)
        self.update_btn=self.button('Обновить',self.check_updates,toolbar)
        self.update_btn.setToolTip('Проверить GitHub Releases и предложить обновление.')
        toolbar.addStretch()
        self.armed = QCheckBox('Включить бинды сценариев'); self.armed.toggled.connect(self.configure_hotkeys); toolbar.addWidget(self.armed)
        outer.addLayout(toolbar)
        settings_card=QFrame(); settings_card.setObjectName('settingsCard')
        preferences=QHBoxLayout(settings_card); preferences.setContentsMargins(12,10,12,10); preferences.setSpacing(10)
        preferences.addWidget(QLabel('Старт, с'))
        self.start_delay=QSpinBox(); self.start_delay.setRange(0,60); self.start_delay.setValue(self.settings['start_delay'])
        self.start_stepper=Stepper(self.start_delay); preferences.addWidget(self.start_stepper)
        preferences.addSpacing(8); preferences.addWidget(QLabel('Запись, с'))
        self.record_delay=QSpinBox(); self.record_delay.setRange(1,60); self.record_delay.setValue(self.settings['record_delay'])
        self.record_stepper=Stepper(self.record_delay); preferences.addWidget(self.record_stepper)
        preferences.addSpacing(8)
        preferences.addWidget(QLabel('Управление:'))
        self.control_bind=QLineEdit(self.settings['control_bind']); self.control_bind.setFixedWidth(120); preferences.addWidget(self.control_bind)
        self.control_apply=self.button('Применить',self.apply_control,preferences)
        preferences.addStretch()
        self.theme=QComboBox(); self.theme.addItem('🎀 Розовая','pink'); self.theme.addItem('🌙 Тёмная','dark')
        self.theme.setCurrentIndex(self.theme.findData(self.settings['theme'])); preferences.addWidget(self.theme)
        outer.addWidget(settings_card)
        self.storage_note=QLabel('Автосохранение: Документы / LisaMacroMagic / settings.json')
        self.storage_note.setObjectName('muted'); self.storage_note.setToolTip(str(self.path)); outer.addWidget(self.storage_note)
        self.start_delay.valueChanged.connect(self.preferences_changed)
        self.record_delay.valueChanged.connect(self.preferences_changed)
        self.theme.currentIndexChanged.connect(self.preferences_changed)
        split = QSplitter(); outer.addWidget(split,1)
        left = QFrame(); left.setObjectName('card'); left_layout = QVBoxLayout(left); left_layout.setContentsMargins(16,16,16,16)
        section=QLabel('♡ Мои сценарии'); section.setObjectName('section'); left_layout.addWidget(section)
        self.list = QListWidget(); self.list.setWordWrap(True); self.list.setSpacing(2); self.list.currentRowChanged.connect(self.select_scenario); left_layout.addWidget(self.list,1)
        row = QHBoxLayout(); self.new_btn = self.button('+ Новый',self.new_scenario,row); self.dup_btn=self.button('Копия',self.duplicate,row); left_layout.addLayout(row)
        self.del_btn = self.button('Удалить сценарий',self.delete_scenario,left_layout)
        split.addWidget(left)
        right = QFrame(); right.setObjectName('card'); body=QVBoxLayout(right); body.setContentsMargins(18,16,18,16)
        form=QFormLayout(); self.name=QLineEdit(); self.bind=QLineEdit(); self.bind.setPlaceholderText('F6 или Ctrl+Alt+K; пусто = без бинда')
        form.addRow('Название',self.name); form.addRow('Горячая клавиша',self.bind); body.addLayout(form)
        self.apply_btn=self.button('Применить название и бинд ♡',self.apply_details,body)
        self.name.textEdited.connect(self.details_edited); self.bind.textEdited.connect(self.details_edited)
        self.steps=QListWidget(); self.steps.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.steps.setObjectName('steps')
        self.steps.setToolTip('Двойной клик — редактировать шаг. Стрелки ниже меняют порядок.')
        self.steps.itemDoubleClicked.connect(self.edit_step); body.addWidget(self.steps,1)
        row=QHBoxLayout(); self.add_btn=self.button('+ Шаг',self.add_step,row); self.edit_btn=self.button('Изменить',self.edit_step,row)
        self.remove_btn=self.button('Удалить',self.remove_step,row); self.up_btn=self.button('↑',lambda:self.move_step(-1),row); self.down_btn=self.button('↓',lambda:self.move_step(1),row); body.addLayout(row)
        self.up_btn.setFixedWidth(40); self.down_btn.setFixedWidth(40)
        self.up_btn.setToolTip('Переместить выбранный шаг выше'); self.down_btn.setToolTip('Переместить выбранный шаг ниже')
        row=QHBoxLayout(); self.run_btn=self.button('▶ Запустить',self.run_current,row,'primary'); self.record_btn=self.button('● Записать действия',self.start_record,row)
        self.stop_btn=self.button('■ Стоп',self.stop_all,row,'stop'); body.addLayout(row)
        self.hint=QLabel(); self.hint.setObjectName('muted'); self.hint.setWordWrap(True); body.addWidget(self.hint)
        split.addWidget(right); split.setSizes([280,750])
        self.status=QLabel('Готово к маленькой магии ♡ Бинды выключены.'); self.status.setObjectName('status'); self.status.setWordWrap(True); outer.addWidget(self.status)
        footer=QHBoxLayout(); self.love_note=QLabel('Made with love ♡'); self.love_note.setObjectName('muted')
        self.love_note.setToolTip(TIME_HINT); footer.addWidget(self.love_note); footer.addStretch()
        self.input_btn=self.button('⌨ Input Monitor',self.show_input_monitor,footer)
        self.diag_btn=self.button('Диагностика',self.copy_diagnostics,footer); self.help_btn=self.button('Как пользоваться',self.help,footer); outer.addLayout(footer)
        self.edit_controls=[self.list,self.name,self.bind,self.apply_btn,self.steps,self.new_btn,self.dup_btn,self.del_btn,self.add_btn,self.edit_btn,self.remove_btn,self.up_btn,self.down_btn,self.open_btn,self.save_btn,self.save_as_btn,self.run_btn,self.record_btn,self.armed]
        self.edit_controls.extend([self.start_delay,self.record_delay,self.control_bind,self.control_apply,self.theme])
        self.edit_controls.extend([self.start_stepper,self.record_stepper])
        self.timer=QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.record_tick)
        self.monitor=QTimer(self); self.monitor.setInterval(200); self.monitor.timeout.connect(self.monitor_record)
        self.details_dirty=False
        self.refresh_list(0)
        self.apply_theme_and_hints()
        if native:
            from hotkeys import Hotkeys
            self.hotkeys=Hotkeys(self.hotkey_received)
            self.configure_hotkeys()
            self.setup_tray()
        QShortcut(QKeySequence('Ctrl+S'),self,activated=self.save_file)
        if self.load_error:
            self.set_status('Файл настроек не загружен и не будет перезаписан автоматически: '+self.load_error)
        else:
            self.autosave()

    def apply_theme_and_hints(self):
        self.setStyleSheet(DARK_STYLE if self.settings['theme']=='dark' else STYLE)
        if self.input_monitor: self.input_monitor.set_theme(self.settings['theme'])
        control=self.settings['control_bind']
        self.stop_btn.setText(f'■ Стоп · {control}')
        self.hint.setText(f'{control}: в простое — вкл/выкл бинды, при записи/выполнении — стоп.\nПри старте 0 с запускай биндом из целевого окна; для кнопки задай задержку.')
        self.start_delay.setToolTip('0 — без отсчёта, запуск по бинду из браузера. От 1 до 60 — время переключиться после кнопки.')
        self.control_bind.setToolTip('Одна клавиша для управления: в простое переключает бинды, в работе останавливает.')
        self.save_btn.setToolTip(str(self.path))

    def preferences_changed(self,*args):
        self.settings.update(start_delay=self.start_delay.value(),record_delay=self.record_delay.value(),theme=self.theme.currentData())
        self.apply_theme_and_hints(); self.changed()

    def apply_control(self):
        candidate=self.control_bind.text().strip()
        previous=self.settings['control_bind']; self.settings['control_bind']=candidate
        try: model.validate(self.data())
        except ValueError as exc:
            self.settings['control_bind']=previous; self.error(exc); return False
        self.apply_theme_and_hints(); self.configure_hotkeys(); self.changed(); return True

    def snapshot(self):
        data=copy.deepcopy(self.data())
        if self.details_dirty and self.current is not None:
            data['scenarios'][self.current].update(name=self.name.text().strip(),bind=self.bind.text().strip())
        return model.validate(data)

    def autosave(self):
        if self.autosave_blocked: return False
        try:
            data=self.snapshot()
            self.path.parent.mkdir(parents=True,exist_ok=True)
            model.save(self.path,data['scenarios'],data['settings'])
        except (OSError,ValueError) as exc:
            self.set_status('Не сохранено автоматически: '+str(exc)); return False
        self.dirty=False
        self.setWindowTitle(WINDOW_TITLE)
        return True

    def button(self,text,slot,layout,style=None):
        button=QPushButton(text); button.clicked.connect(slot)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(36)
        if style: button.setObjectName(style)
        layout.addWidget(button); return button

    def fox_clicked(self):
        if self.busy(): self.secret_clicks=0; return
        if not self.secret_timer.isValid() or self.secret_timer.elapsed()>4000:
            self.secret_clicks=0; self.secret_timer.start()
        self.secret_clicks+=1
        if self.secret_clicks==7:
            self.secret_clicks=0; self.secret_timer.invalidate()
            if self.date_dialog is None: self.date_dialog=DateIdeaDialog(self)
            self.date_dialog.show(); self.date_dialog.raise_(); self.date_dialog.activateWindow()

    def show_input_monitor(self):
        from input_monitor import Monitor
        if self.input_monitor is None:
            self.input_monitor=Monitor(self,theme=self.settings['theme'])
            self.input_monitor.setWindowIcon(icon())
        self.input_monitor.showNormal(); self.input_monitor.raise_(); self.input_monitor.activateWindow()
        self.input_monitor.surface.setFocus()

    def allowed_test_windows(self):
        return {int(self.input_monitor.winId())} if self.input_monitor and self.input_monitor.isVisible() else set()

    def check_updates(self,startup=False):
        if self.downloading or self.update_checker.reply is not None: return
        if self.release and not startup: self.offer_update(); return
        self.startup_check=startup
        self.update_btn.setEnabled(False)
        self.update_btn.setText('Проверяю…')
        self.update_checker.check()

    def update_finished(self,release,message):
        self.release=release
        self.update_btn.setText(f'Обновить до {release[0]}' if release else 'Обновить')
        self.update_btn.setEnabled(True)
        if not self.busy() and (release or not self.startup_check): self.set_status(message)
        self.update_btn.setToolTip(message)
        if release and self.isVisible() and not self.busy(): self.offer_update()

    def offer_update(self):
        if self.busy() or self.downloading or not self.release: return
        if not getattr(sys,'frozen',False):
            self.set_status(f'Доступна версия {self.release[0]}. Самообновление доступно из EXE.'); return
        dialog=QMessageBox(QMessageBox.Icon.Question,'Обновление 🎀',f'Доступна версия {self.release[0]}. Скачать, заменить текущий EXE и перезапустить приложение?',parent=self)
        install=dialog.addButton('Обновить',QMessageBox.ButtonRole.AcceptRole)
        manual=dialog.addButton('Скачать вручную',QMessageBox.ButtonRole.ActionRole)
        cancel=dialog.addButton('Позже',QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton()==manual: self.open_release(); return
        if dialog.clickedButton()!=install: return
        self.downloading=True
        self.update_btn.setEnabled(False); self.update_btn.setText('Загрузка: 0%')
        self.update_checker.download(self.release,Path(sys.executable).resolve())

    def update_progress(self,received,total):
        if self.downloading and total>0:
            self.update_btn.setText(f'Загрузка: {min(100,received*100//total)}%')

    def open_release(self):
        url=self.release[1].rsplit('/',1)[0].replace('/releases/download/','/releases/tag/') if self.release else RELEASE_URL.rsplit('tag/',1)[0]+'latest'
        QDesktopServices.openUrl(QUrl(url))

    def update_downloaded(self,stage,error):
        self.downloading=False
        self.update_btn.setEnabled(True); self.update_btn.setText('Обновить')
        if error:
            dialog=QMessageBox(QMessageBox.Icon.Warning,'Обновление не скачано',error,parent=self)
            manual=dialog.addButton('Скачать вручную',QMessageBox.ButtonRole.ActionRole)
            close=dialog.addButton('Закрыть',QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(close)
            dialog.exec()
            if dialog.clickedButton()==manual: self.open_release()
            return
        self.update_stage=stage
        self.exit_from_tray()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray=QSystemTrayIcon(self.windowIcon(),self)
        self.tray_menu=QMenu(self)
        self.tray_menu.addAction('Открыть Lisa’s Macro Magic',self.restore_from_tray)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction('Выйти',self.exit_from_tray)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.update_tray()
        self.tray.show()

    def update_tray(self):
        if self.tray is None: return
        state=('Идёт запись' if self.recorder else 'Подготовка записи' if self.pending_record else
               f'В работе: {len(self.playbacks)}' if self.playbacks else 'Бинды включены' if self.armed.isChecked() else 'Бинды выключены')
        self.tray.setToolTip(f'Lisa’s Macro Magic 🎀\n{state}')

    def tray_activated(self,reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        self.show()
        if self.isMinimized(): self.showNormal()
        self.raise_(); self.activateWindow()

    def exit_from_tray(self):
        self.exit_requested=True
        self.close()

    def set_status(self,text): self.status.setText(text); self.update_tray()
    def error(self,exc): QMessageBox.warning(self,'Проверим настройки 🎀',str(exc))
    def data(self): return {'format':1,'scenarios':self.scenarios,'settings':self.settings}
    def selected(self): return self.scenarios[self.current] if self.current is not None else None
    def changed(self):
        self.dirty=True
        self.setWindowTitle(f'{WINDOW_TITLE} *')
        self.auto_timer.start()

    def details_edited(self): self.details_dirty=True; self.changed()

    def refresh_list(self,row):
        self.list.blockSignals(True); self.list.clear()
        for s in self.scenarios: self.list.addItem(f"{s['name']}\n{s['bind'] or 'Без бинда'}  ·  {len(s['steps'])} шагов")
        self.list.setCurrentRow(row); self.list.blockSignals(False)
        self.current=row if 0 <= row < len(self.scenarios) else None
        self.show_selected()

    def show_selected(self):
        item=self.selected(); self.details_dirty=False
        self.name.setText(item['name'] if item else ''); self.bind.setText(item['bind'] if item else '')
        self.refresh_steps()

    def select_scenario(self,row):
        if self.details_dirty and not self.apply_details(refresh=False):
            self.list.blockSignals(True); self.list.setCurrentRow(self.current if self.current is not None else -1); self.list.blockSignals(False); return
        self.current=row if 0 <= row < len(self.scenarios) else None
        self.show_selected()

    def refresh_steps(self,row=-1):
        self.steps.clear()
        item=self.selected()
        if item:
            names={scenario['id']:scenario['name'] for scenario in self.scenarios}
            for i,step in enumerate(item['steps'],1):
                called_name=names.get(step['scenario_id']) if step['type']=='call' else None
                description=model.describe(step,called_name)
                self.steps.addItem(f'{i:02d}   {description}')
            if self.list.item(self.current):
                self.list.item(self.current).setText(f"{item['name']}\n{item['bind'] or 'Без бинда'}  ·  {len(item['steps'])} шагов")
        self.steps.setCurrentRow(row)

    def apply_details(self,checked=False,refresh=True):
        item=self.selected()
        if not item: return True
        old=(item['name'],item['bind'])
        item['name']=self.name.text().strip(); item['bind']=self.bind.text().strip()
        try: model.validate(self.data())
        except ValueError as exc:
            item['name'],item['bind']=old; self.error(exc); return False
        self.details_dirty=False
        if old!=(item['name'],item['bind']): self.changed()
        if refresh: self.refresh_list(self.current)
        self.configure_hotkeys(); return True

    def new_scenario(self):
        if not self.apply_details(): return
        if len(self.scenarios)>=100: self.error('Не более 100 сценариев.'); return
        self.scenarios.append(model.scenario()); self.changed(); self.refresh_list(len(self.scenarios)-1)

    def duplicate(self):
        if not self.selected() or not self.apply_details(): return
        if len(self.scenarios)>=100: return self.error('Не более 100 сценариев.')
        source=copy.deepcopy(self.selected()); new=model.scenario((source['name']+' — копия')[:100]); new['steps']=source['steps']
        self.scenarios.append(new); self.changed(); self.refresh_list(len(self.scenarios)-1)

    def delete_scenario(self):
        selected=self.selected()
        if not selected: return
        for item in self.scenarios:
            if any(step['type']=='call' and step['scenario_id']==selected['id'] for step in item['steps']):
                return self.error(f"Сначала убери этот вызов из сценария «{item['name']}».")
        if QMessageBox.question(self,'Удалить сценарий?','Удалить выбранный сценарий из текущего проекта?')==QMessageBox.StandardButton.Yes:
            self.scenarios.pop(self.current); self.changed(); self.refresh_list(0 if self.scenarios else -1); self.configure_hotkeys()

    def call_targets(self):
        return [(item['id'],f"{index+1}. {item['name']}")
                for index,item in enumerate(self.scenarios) if index!=self.current]

    def add_step(self):
        if not self.selected(): return
        dialog=StepDialog(parent=self,call_targets=self.call_targets())
        if dialog.exec():
            steps=self.selected()['steps'].copy(); row=self.steps.currentRow()+1 if self.steps.currentRow()>=0 else len(steps)
            steps.insert(row,dialog.result_step()); self.replace_steps(steps,row)

    def edit_step(self,*args):
        row=self.steps.currentRow()
        if not self.selected() or row<0: return
        dialog=StepDialog(self.selected()['steps'][row],self,call_targets=self.call_targets())
        if dialog.exec():
            steps=self.selected()['steps'].copy()
            steps[row]=dialog.result_step(); self.replace_steps(steps,row)

    def remove_step(self):
        row=self.steps.currentRow()
        if row>=0 and self.selected():
            steps=self.selected()['steps'].copy()
            steps.pop(row); self.replace_steps(steps,row)

    def move_step(self,delta):
        row=self.steps.currentRow(); item=self.selected()
        if item and 0<=row+delta<len(item['steps']) and row>=0:
            steps=item['steps'].copy()
            steps[row],steps[row+delta]=steps[row+delta],steps[row]
            self.replace_steps(steps,row+delta)

    def replace_steps(self,steps,row):
        selected=self.selected()
        try:
            model.validate_repeats(steps)
            model.validate_calls([{**item,'steps':steps} if item is selected else item for item in self.scenarios])
        except ValueError as exc: return self.error(exc)
        selected['steps']=steps
        self.changed(); self.refresh_steps(row)

    def configure_hotkeys(self,*args):
        if not self.hotkeys: return
        try: self.hotkeys.configure(self.scenarios if self.armed.isChecked() else [],self.settings['control_bind'])
        except Exception as exc:
            self.armed.blockSignals(True); self.armed.setChecked(False); self.armed.blockSignals(False)
            self.set_status('Бинды недоступны: '+str(exc)); return
        self.set_status(('Бинды включены ♡' if self.armed.isChecked() else 'Бинды выключены.')+f" {self.settings['control_bind']} — переключить / остановить")

    def hotkey_received(self,action):
        if action=='control' and self.request_playback_stop():
            action='stop'
        self.bridge.action.emit(action)

    def handle_action(self,action):
        if action=='stop':
            if self.stopping_playback: self.set_status('Останавливаю сценарии…')
        elif action=='control':
            if self.busy(): self.stop_all()
            else: self.armed.setChecked(not self.armed.isChecked())
        elif self.armed.isChecked():
            item=next((s for s in self.scenarios if s['id']==action),None)
            if item: self.run_scenario(item,triggered=True)

    def busy(self): return bool(self.playbacks or self.recorder or self.pending_record)
    def begin_emergency(self):
        if self.hotkeys and (not self.hotkeys.listener or not self.hotkeys.listener.is_alive()):
            raise RuntimeError('Управляющая клавиша недоступна. Перезапусти приложение.')

    def end_emergency(self):
        pass

    def set_busy(self,value):
        for control in self.edit_controls: control.setEnabled(not value)

    def run_current(self):
        if self.apply_details() and self.selected(): self.run_scenario(self.selected())

    def run_scenario(self,item,triggered=False):
        scenario_id=item['id']
        if self.recorder or self.pending_record or self.stopping_playback or scenario_id in self.playbacks: return
        if self.details_dirty:
            self.set_status('Сначала примени изменения названия и бинда.'); return
        try:
            model.validate(self.data())
            if not item['steps']: raise ValueError('Добавь хотя бы один шаг.')
            self.begin_emergency()
        except (ValueError,RuntimeError) as exc:
            if triggered: self.set_status(f"{item['name']} · {exc}")
            else: self.error(exc)
            return
        scenarios=copy.deepcopy({scenario['id']:scenario for scenario in self.scenarios})
        player=Player(scenarios[scenario_id]['steps'],
            lambda text:self.bridge.status.emit(scenario_id,text),
            lambda text:self.bridge.finished.emit(scenario_id,text),
            stop_label=self.settings['control_bind'],trigger_modifiers=model.hotkey(item['bind'])[0] if triggered and item['bind'] else 0,
            allowed_windows=self.allowed_test_windows(),input_lock=self.input_lock,scenarios=scenarios)
        with self.playback_lock:
            if self.stopping_playback: return
            self.playbacks[scenario_id]=(item['name'],player)
        self.set_busy(True)
        self.play_status(scenario_id,'Запуск…')
        delay=self.settings['start_delay']
        worker=threading.Thread(target=lambda:player.run(countdown=delay),daemon=False)
        try: worker.start()
        except RuntimeError as exc: self.play_finished(scenario_id,str(exc))

    def play_status(self,scenario_id,text):
        if scenario_id in self.playbacks and not self.stopping_playback:
            name,_=self.playbacks[scenario_id]
            self.show_playback_status(name,text)

    def show_playback_status(self,name,text):
        count=f' · В работе: {len(self.playbacks)}' if self.playbacks else ''
        self.set_status(f'{name} · {text}{count}')

    def play_finished(self,scenario_id,text):
        with self.playback_lock:
            playback=self.playbacks.pop(scenario_id,None)
            if not self.playbacks: self.stopping_playback=False
        if playback is None: return
        if not self.playbacks:
            self.end_emergency(); self.set_busy(False)
        self.show_playback_status(playback[0],text)
        if self.close_pending and not self.playbacks:
            self.close_pending=False; self.close()

    def start_record(self):
        if self.busy() or not self.selected() or not self.apply_details(): return
        answer=QMessageBox.question(self,'Запись действий 🎀',
            f"После отсчёта записываются клавиши и мышь в выбранном окне.\nНе вводи пароли и личные данные. Запись сохраняется в Документы.\n{self.settings['control_bind']} — закончить запись. Добавить её в конец сценария?")
        if answer!=QMessageBox.StandardButton.Yes: return
        try: self.begin_emergency()
        except Exception as exc: return self.error(exc)
        self.record_target=self.selected()['id']; self.pending_record=self.settings['record_delay']; self.set_busy(True)
        self.set_status(f"Запись через {self.pending_record}… переключись в нужное окно. {self.settings['control_bind']} — отмена"); self.timer.start()

    def record_tick(self):
        self.pending_record-=1
        if self.pending_record:
            self.set_status(f'Запись через {self.pending_record}… переключись в нужное окно.'); return
        self.timer.stop()
        try:
            self.recorder=Recorder(self.bridge.record_stop.emit,control_signature=model.hotkey(self.settings['control_bind']),
                allowed_windows=self.allowed_test_windows()); self.recorder.start()
            self.monitor.start(); self.set_status(f"● Идёт запись · {self.settings['control_bind']} — закончить")
        except Exception as exc:
            if self.recorder: self.recorder.stop()
            self.recorder=None; self.end_emergency(); self.set_busy(False); self.error(exc)

    def monitor_record(self):
        if not self.recorder: return
        if foreground()[0]!=self.recorder.target:
            self.finish_record('Запись остановлена: активное окно сменилось.')
        elif not self.recorder.active:
            self.finish_record('Запись завершена: достигнут предел или окно сменилось.')
        elif any(not listener.is_alive() for listener in self.recorder.listeners):
            self.finish_record('Запись остановлена: обработчик ввода завершился.')

    def finish_record(self,message='Запись завершена ♡'):
        if not self.recorder and not self.pending_record: return
        self.timer.stop(); self.monitor.stop(); self.pending_record=0
        recorder,self.recorder=self.recorder,None
        if recorder:
            steps=recorder.stop(); item=next((s for s in self.scenarios if s['id']==self.record_target),None)
            if item:
                old=copy.deepcopy(item['steps']); item['steps'].extend(steps)
                try: model.validate(self.data())
                except ValueError as exc: item['steps']=old; self.error('Запись не добавлена: '+str(exc))
                else: self.changed(); self.refresh_steps()
        self.end_emergency(); self.set_busy(False); self.set_status(message)

    def request_playback_stop(self):
        with self.playback_lock:
            if not self.playbacks: return False
            if not self.stopping_playback:
                self.stopping_playback=True
                for _,player in self.playbacks.values(): player.stop()
            return True

    def stop_all(self):
        if self.request_playback_stop(): self.set_status('Останавливаю сценарии…')
        elif self.recorder or self.pending_record: self.finish_record('Запись остановлена. Действия добавлены в сценарий.')

    def confirm_discard(self):
        if not self.dirty: return True
        answer=QMessageBox.question(self,'Несохранённая магия','Сохранить изменения?',QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Save: return self.save_file()
        return answer==QMessageBox.StandardButton.Discard

    def open_file(self):
        if self.busy() or not self.confirm_discard(): return
        path,_=QFileDialog.getOpenFileName(self,'Открыть сценарии','','Lisa Macro Magic (*.json)')
        if not path: return
        try: project=model.load_project(Path(path))
        except (OSError,ValueError,TypeError,RecursionError) as exc: return self.error(exc)
        self.armed.setChecked(False); self.scenarios=project['scenarios']; self.settings=project['settings']
        for widget,value in [(self.start_delay,self.settings['start_delay']),(self.record_delay,self.settings['record_delay'])]:
            widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)
        self.theme.blockSignals(True); self.theme.setCurrentIndex(self.theme.findData(self.settings['theme'])); self.theme.blockSignals(False)
        self.control_bind.setText(self.settings['control_bind']); self.apply_theme_and_hints()
        self.refresh_list(0 if self.scenarios else -1); self.configure_hotkeys(); self.changed()
        self.autosave(); self.set_status('Проект импортирован. Бинды выключены ♡')

    def save_file(self,save_as=False):
        if self.busy() or not self.apply_details(): return False
        path=self.path
        if save_as:
            selected,_=QFileDialog.getSaveFileName(self,'Сохранить сценарии',str(path or 'Lisa_scenarios.json'),'JSON (*.json)')
            if not selected: return False
            path=Path(selected)
            if path.suffix.lower()!='.json': path=path.with_suffix('.json')
        if not save_as and self.autosave_blocked:
            if QMessageBox.question(self,'Заменить повреждённый файл?',f'Автозагрузка не удалась. Заменить файл текущими настройками?\n{path}')!=QMessageBox.StandardButton.Yes: return False
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            model.save(path,self.scenarios,self.settings)
        except (OSError,ValueError) as exc: self.error(exc); return False
        if not save_as: self.autosave_blocked=False; self.dirty=False
        self.setWindowTitle(WINDOW_TITLE); self.set_status(f'Сохранено ♡ {path}'); return True

    def copy_diagnostics(self):
        import platform,struct,tempfile
        result='OK'
        try:
            with tempfile.TemporaryFile() as f: f.write(b'test'); f.seek(0); assert f.read()==b'test'
        except OSError: result='Ошибка доступа к TEMP'
        report=f"Lisa Macro Magic {VERSION}\nWindows: {platform.platform()}\nОС: {platform.machine()}\nПроцесс: {struct.calcsize('P')*8} bit\nПуть: {sys.executable if getattr(sys,'frozen',False) else Path(__file__).resolve()}\nTEMP: {result}"
        QApplication.clipboard().setText(report); self.set_status('Диагностика скопирована ♡')

    def help(self):
        QMessageBox.information(self,'Как творить магию 🎀',
            '1. Создай сценарий, укажи название и свободный бинд, нажми «Применить».\n'
            '2. Добавь шаги; двойной клик редактирует, стрелки меняют порядок.\n'
            '3. JSON автоматически сохраняется в Документы / LisaMacroMagic / settings.json.\n'
            '4. Старт 0 с — по бинду из браузера; для кнопки задай задержку.\n'
            f"5. {self.settings['control_bind']}: в простое переключить бинды, в работе — стоп. Клавишу можно изменить.\n\n"
            'Крестик прячет окно в трей. Чтобы завершить приложение, выбери «Выйти» в меню значка лисички.\n\n'
            '«Ждать ручной ЛКМ» продолжает после твоего клика и отпускания кнопки.\n'
            'Координаты кликов можно получить записью движений и затем отредактировать.\n'
            '«Клик под курсором» нажимает без заданных координат. «Повторить предыдущее действие» работает и после паузы.\n'
            '«Выполнить сценарий» добавляет другой макрос в текущий. После него выполняется следующий шаг.\n'
            'Пока сценарий ждёт, другой сценарий можно запустить его биндом. «Стоп» останавливает все запуски.\n'
            'Если исходное окно не вернётся за 0,3 с, сценарий остановится. При записи остановка происходит сразу.\n'
            'Roadcons настраивается тобой: программа не распознаёт объекты карты.\n'
            'Она не проверяет результат команды в браузере — сначала проверяй сценарий на безопасном примере.')

    def closeEvent(self,event):
        application=QApplication.instance()
        if self.tray is not None and self.tray.isVisible() and not self.exit_requested and not application.isSavingSession():
            event.ignore()
            if self.input_monitor: self.input_monitor.close()
            if self.date_dialog: self.date_dialog.close()
            self.hide()
            return
        if self.downloading:
            self.set_status('Подожди, пока завершится загрузка обновления.')
            self.exit_requested=False; event.ignore(); return
        if self.playbacks:
            self.close_pending=True; self.stop_all(); event.ignore(); return
        if self.recorder or self.pending_record: self.finish_record('Запись завершена.')
        self.auto_timer.stop()
        if self.dirty: self.autosave()
        if self.dirty and self.isHidden() and self.exit_requested: self.restore_from_tray()
        if not self.confirm_discard():
            if self.update_stage:
                update_install.cleanup(self.update_stage,Path(sys.executable).resolve()); self.update_stage=None
            self.exit_requested=False
            event.ignore(); return
        if self.update_stage:
            target=Path(sys.executable).resolve()
            try: update_install.start_install(self.update_stage,target)
            except OSError as exc:
                update_install.cleanup(self.update_stage,target); self.update_stage=None
                self.exit_requested=False; self.error('Не удалось подготовить замену EXE: '+str(exc)); event.ignore(); return
            self.update_stage=None
        if self.hotkeys: self.hotkeys.clear()
        if self.input_monitor: self.input_monitor.close()
        if self.date_dialog: self.date_dialog.close()
        self.affirmation.timer.stop()
        self.end_emergency()
        if self.tray is not None: self.tray.hide()
        event.accept()
        if self.exit_requested: QTimer.singleShot(0,application.quit)


def main():
    if sys.platform!='win32': raise SystemExit('Windows x64 required')
    if getattr(sys,'frozen',False) and len(sys.argv)==4 and sys.argv[1]=='--apply-update':
        return update_install.helper_main(*sys.argv[2:])
    # Match physical screen coordinates used by the Windows input backend.
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError,AttributeError): pass
    app=QApplication(sys.argv); app.setFont(QFont('Segoe UI',10)); app.setApplicationVersion(VERSION)
    window=Window(); window.show()
    QTimer.singleShot(700,lambda:window.check_updates(startup=True))
    if getattr(sys,'frozen',False) and len(sys.argv)==3 and sys.argv[1]=='--update-cleanup':
        remaining=20
        target=Path(sys.executable).resolve()
        def clean_update():
            nonlocal remaining
            if window.busy() or window.downloading:
                QTimer.singleShot(1000,clean_update); return
            remaining-=1
            if not update_install.cleanup(sys.argv[2],target) and remaining:
                QTimer.singleShot(1000,clean_update)
                return
            # Versions through 0.5.15 launch the new build under the old filename.
            if target.name.casefold()!=update_install.EXE_NAME.casefold():
                try: window.update_stage=update_install.stage_name_migration(target)
                except OSError as exc: window.set_status(f'Не удалось сменить имя EXE: {exc}'); return
                window.exit_from_tray()
        QTimer.singleShot(1000,clean_update)
    return app.exec()


if __name__=='__main__': sys.exit(main())
