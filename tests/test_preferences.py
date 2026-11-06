import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from PySide6.QtWidgets import QApplication
import app,model,storage


class PreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'Docs'/'LisaMacroMagic'/'settings.json'
        self.windows=[]

    def window(self):
        w=app.Window(native=False,persistence_path=self.path); self.windows.append(w); return w

    def tearDown(self):
        for w in self.windows:
            w.player=None; w.worker=None; w.dirty=False; w.close()
        self.temp.cleanup()

    def test_first_start_creates_file_and_zero_delay(self):
        w=self.window()
        self.assertTrue(self.path.exists()); self.assertEqual(w.start_delay.value(),0)
        self.assertEqual(model.load_project(self.path)['settings']['control_bind'],'F12')

    def test_settings_macros_and_theme_restore(self):
        w=self.window(); w.start_delay.setValue(5); w.record_delay.setValue(2)
        w.theme.setCurrentIndex(w.theme.findData('dark'))
        w.control_bind.setText('F11'); self.assertTrue(w.apply_control())
        w.new_scenario(); w.name.setText('Мой второй'); w.bind.setText('F7'); w.apply_details()
        self.assertTrue(w.autosave()); w.dirty=False; w.close()
        restored=self.window()
        self.assertEqual(restored.settings,{'start_delay':5,'record_delay':2,'theme':'dark','control_bind':'F11'})
        self.assertEqual(restored.scenarios[1]['name'],'Мой второй')
        self.assertFalse(restored.armed.isChecked())

    def test_control_conflicts_and_f11_is_available(self):
        w=self.window(); w.control_bind.setText('F6')
        with patch.object(w,'error'): self.assertFalse(w.apply_control())
        self.assertEqual(w.settings['control_bind'],'F12')
        w.bind.setText('F11'); self.assertTrue(w.apply_details())

    def test_control_toggles_when_idle_and_stops_busy_without_toggling(self):
        w=self.window(); w.handle_action('toggle'); self.assertTrue(w.armed.isChecked())
        w.player=MagicMock(); w.hotkey_received('control'); self.application.processEvents()
        w.player.stop.assert_called(); self.assertTrue(w.armed.isChecked()); w.player=None

    def test_bad_file_is_preserved(self):
        self.path.parent.mkdir(parents=True); self.path.write_text('{bad',encoding='utf-8')
        w=self.window(); w.start_delay.setValue(7)
        self.assertFalse(w.autosave()); self.assertTrue(w.autosave_blocked)
        self.assertEqual(self.path.read_text(),'{bad')

    def test_invalid_draft_does_not_overwrite_valid_file(self):
        w=self.window(); original=self.path.read_bytes()
        w.name.setText(''); w.details_dirty=True
        self.assertFalse(w.autosave()); self.assertEqual(self.path.read_bytes(),original)
        w.details_dirty=False

    def test_save_as_is_export_and_default_path_stays(self):
        w=self.window(); exported=Path(self.temp.name)/'export.json'
        with patch('app.QFileDialog.getSaveFileName',return_value=(str(exported),'JSON')):
            self.assertTrue(w.save_file(True))
        self.assertEqual(w.path,self.path); self.assertEqual(model.load(exported),w.scenarios)

    def test_old_project_migrates_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"format":1,"scenarios":[]}',encoding='utf-8')
        w=self.window(); self.assertEqual(w.scenarios,[]); self.assertEqual(w.settings['start_delay'],0)

    def test_default_documents_location(self):
        with patch('storage.QStandardPaths.writableLocation',return_value=str(Path(self.temp.name)/'Redirected')):
            self.assertEqual(storage.default_path(),Path(self.temp.name)/'Redirected'/'LisaMacroMagic'/'settings.json')

    def test_player_receives_selected_countdown(self):
        w=self.window(); w.start_delay.setValue(6)
        with patch('app.Player') as player,patch('app.threading.Thread') as thread:
            w.run_scenario(w.selected())
            thread.call_args.kwargs['target']()
            player.return_value.run.assert_called_once_with(countdown=6)
            w.play_finished('test')

    def test_animation_has_frames(self):
        w=self.window(); self.assertTrue(w.fox.movie.isValid()); self.assertGreater(w.fox.movie.frameCount(),1)
        self.assertFalse(w.windowIcon().isNull())
