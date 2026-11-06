import os,tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
import app


class SecretTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.window=app.Window(native=False,persistence_path=Path(self.temp.name)/'settings.json')

    def tearDown(self):
        self.window.pending_record=0; self.window.dirty=False; self.window.close(); self.temp.cleanup()

    def test_seven_fox_clicks_open_only_local_secret(self):
        w=self.window
        before=w.path.read_bytes()
        for _ in range(6): QTest.mouseClick(w.fox,Qt.MouseButton.LeftButton)
        self.assertIsNone(w.date_dialog)
        QTest.mouseClick(w.fox,Qt.MouseButton.LeftButton)
        self.assertTrue(w.date_dialog.isVisible())
        self.assertEqual(w.date_dialog.emojis.text(),'👫')
        self.assertEqual(w.date_dialog.flag.accessibleName(),'🇯🇵')
        self.assertEqual(w.date_dialog.title.text(),'date idea?')
        self.assertEqual(w.path.read_bytes(),before)

    def test_secret_does_not_open_while_recording(self):
        w=self.window; w.pending_record=2
        for _ in range(7): w.fox_clicked()
        self.assertIsNone(w.date_dialog)
