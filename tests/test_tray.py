import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
import app


class TrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.window=app.Window(native=False,persistence_path=Path(self.temp.name)/'settings.json')
        self.window.tray=Mock()
        self.window.tray.isVisible.return_value=True
        self.window.hotkeys=Mock()

    def tearDown(self):
        self.window.tray=None
        self.window.hotkeys=None
        self.window.player=None
        self.window.exit_requested=False
        self.window.dirty=False
        self.window.close()
        self.temp.cleanup()

    def test_close_hides_window_but_leaves_macro_and_hotkeys_running(self):
        w=self.window
        w.show(); w.armed.setChecked(True)
        w.player=Mock()
        w.close()
        self.assertFalse(w.isVisible())
        self.assertTrue(w.armed.isChecked())
        self.assertTrue(w.affirmation.timer.isActive())
        w.player.stop.assert_not_called()
        w.hotkeys.clear.assert_not_called()
        w.restore_from_tray()
        self.assertTrue(w.isVisible())

    def test_exit_stops_macro_then_removes_tray_and_hotkeys(self):
        w=self.window; player=Mock(); w.player=player
        with patch.object(app.QTimer,'singleShot') as quit_later:
            w.exit_from_tray()
            player.stop.assert_called_once()
            w.tray.hide.assert_not_called()
            quit_later.assert_not_called()
            w.play_finished('Готово')
            w.tray.hide.assert_called_once()
            w.hotkeys.clear.assert_called_once()
            quit_later.assert_called_once_with(0,self.application.quit)

    def test_cancelled_exit_preserves_tray_mode(self):
        w=self.window
        with patch.object(w,'confirm_discard',return_value=False):
            w.exit_from_tray()
        self.assertFalse(w.exit_requested)
        w.tray.hide.assert_not_called()
        w.hotkeys.clear.assert_not_called()
