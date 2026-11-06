import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog
import app


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'LisaMacroMagic'/'settings.json'
        self.window=app.Window(native=False,persistence_path=self.path)
    def tearDown(self): self.window.dirty=False; self.window.close(); self.temp.cleanup()

    def test_multiple_scenarios_and_bind_conflict(self):
        w=self.window; w.new_scenario(); w.name.setText('Другой'); w.bind.setText('F7'); self.assertTrue(w.apply_details())
        self.assertEqual([s['bind'] for s in w.scenarios],['F6','F7'])
        w.bind.setText('F6')
        with patch.object(w,'error') as error: self.assertFalse(w.apply_details()); error.assert_called_once()
        self.assertEqual(w.scenarios[1]['bind'],'F7')

    def test_step_reorder_and_delete(self):
        w=self.window; w.steps.setCurrentRow(0); w.move_step(1)
        self.assertEqual(w.selected()['steps'][0]['type'],'wait_click')
        w.remove_step(); self.assertEqual(len(w.selected()['steps']),3)

    def test_duplicate_copies_steps_without_bind(self):
        w=self.window; w.duplicate(); self.assertEqual(w.scenarios[1]['bind'],'')
        w.scenarios[1]['steps'][0]['value']='s'
        self.assertEqual(w.scenarios[0]['steps'][0]['value'],'z')

    def test_wait_click_dialog(self):
        dialog=app.StepDialog({'type':'wait_click','seconds':120})
        self.assertEqual(dialog.result_step(),{'type':'wait_click','seconds':120})
        dialog.close()

    def test_time_hint_only_in_deck_and_footer_tooltip(self):
        from affirmations import TIME_HINT,PHRASES
        self.assertEqual(self.window.love_note.toolTip(),TIME_HINT)
        self.assertIn(TIME_HINT,PHRASES)
        self.assertFalse(hasattr(self.window.affirmation,'time_hint'))

    def test_wait_key_dialog_defaults_and_edit(self):
        dialog=app.StepDialog()
        dialog.kind.setCurrentIndex(dialog.kind.findData('wait_key'))
        self.assertEqual(dialog.result_step(),{'type':'wait_key','value':'space','seconds':120})
        dialog.close()
        saved={'type':'wait_key','value':'enter','seconds':60}
        dialog=app.StepDialog(saved)
        self.assertEqual(dialog.result_step(),saved); dialog.close()

    def test_busy_disables_editor(self):
        w=self.window; w.set_busy(True)
        self.assertFalse(w.run_btn.isEnabled()); self.assertFalse(w.open_btn.isEnabled()); self.assertTrue(w.stop_btn.isEnabled())

    def test_stop_during_record_countdown(self):
        w=self.window; w.pending_record=3; w.set_busy(True); w.stop_all()
        self.assertEqual(w.pending_record,0); self.assertIsNone(w.recorder); self.assertTrue(w.run_btn.isEnabled())
