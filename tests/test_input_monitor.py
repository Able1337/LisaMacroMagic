import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
import app
from input_monitor import Monitor


class InputMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.window=app.Window(native=False,persistence_path=Path(self.temp.name)/'settings.json')
        self.window.show_input_monitor(); self.monitor=self.window.input_monitor
        self.application.processEvents(); self.monitor.clear_log()

    def tearDown(self): self.window.dirty=False; self.window.close(); self.temp.cleanup()

    def test_keyboard_combinations_and_releases_without_triggering_main_save(self):
        with patch('app.model.save') as save:
            QTest.keyClick(self.monitor.surface,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
            QTest.keyClick(self.monitor.surface,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
            self.application.processEvents(); save.assert_not_called()
        text=self.monitor.log.toPlainText()
        self.assertIn('Ctrl+Shift+S',text); self.assertIn('↑ ОТПУЩЕНО',text); self.assertIn('VK=',text)

    def test_mouse_buttons_and_wheel(self):
        for button in (Qt.MouseButton.LeftButton,Qt.MouseButton.RightButton,Qt.MouseButton.MiddleButton):
            QTest.mouseClick(self.monitor.surface,button,pos=QPoint(20,20))
        event=QWheelEvent(QPointF(20,20),QPointF(100,100),QPoint(0,0),QPoint(0,120),
            Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        self.application.sendEvent(self.monitor.surface,event)
        text=self.monitor.log.toPlainText()
        for label in ('ЛКМ','ПКМ','СКМ','ПРОКРУТКА','экран='): self.assertIn(label,text)

    def test_events_in_editor_are_not_logged(self):
        count=self.monitor.sequence
        QTest.keyClick(self.window.name,Qt.Key.Key_A)
        self.assertEqual(self.monitor.sequence,count)

    def test_close_reopen_reuses_window_without_duplicate_events(self):
        original=self.monitor
        self.monitor.close(); self.assertFalse(self.monitor.filter_active)
        self.assertEqual(self.window.allowed_test_windows(),set())
        self.window.show_input_monitor(); self.assertIs(self.window.input_monitor,original)
        self.application.processEvents(); self.monitor.clear_log()
        QTest.keyClick(self.monitor.surface,Qt.Key.Key_Z)
        self.assertEqual(self.monitor.sequence,2)
        self.assertEqual(self.window.allowed_test_windows(),{int(self.monitor.winId())})

    def test_clipboard_clear_and_bounded_log(self):
        QTest.keyClick(self.monitor.surface,Qt.Key.Key_Z)
        self.monitor.copy_log(); self.assertIn('Z',self.application.clipboard().text())
        self.assertEqual(self.monitor.log.maximumBlockCount(),5000)
        self.monitor.clear_log(); self.assertEqual(self.monitor.sequence,0); self.assertEqual(self.monitor.log.toPlainText(),'')

    def test_theme_matches_parent_and_shutdown_closes_monitor(self):
        self.window.theme.setCurrentIndex(self.window.theme.findData('dark'))
        self.assertIn('#241c2c',self.monitor.styleSheet())
        self.window.dirty=False; self.window.close()
        self.assertFalse(self.monitor.isVisible()); self.assertFalse(self.monitor.filter_active)
