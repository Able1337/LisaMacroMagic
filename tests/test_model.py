import json
import tempfile
import unittest
from pathlib import Path
import model


class ModelTests(unittest.TestCase):
    def data(self): return {'format':1,'scenarios':[model.scenario('Карта','Ctrl+Alt+K')]}

    def test_roundtrip_multiple_binds(self):
        data=self.data(); data['scenarios'].append(model.scenario('Второй','F7'))
        data['scenarios'][0]['steps']=[{'type':'keys','value':'z'},{'type':'wait_click','seconds':120},{'type':'keys','value':'ctrl+shift+s'}]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'сценарии.json'; model.save(path,data['scenarios'])
            self.assertEqual(model.load(path),data['scenarios'])
            self.assertEqual(len(list(Path(d).iterdir())),1)

    def test_conflict_case_and_modifier_order(self):
        data=self.data(); data['scenarios'].append(model.scenario('Другое','alt+ctrl+k'))
        with self.assertRaises(ValueError): model.validate(data)

    def test_function_hotkeys_and_plain_letter(self):
        for value in ('k','Ctrl+Ctrl+K','Ctrl+Shift'):
            with self.subTest(value=value), self.assertRaises(ValueError): model.hotkey(value)
        self.assertEqual(model.hotkey('F6'),(0,117))
        self.assertEqual(model.hotkey('Ctrl+Alt+K'),(3,75))
        self.assertEqual(model.hotkey('F12'),(0,123))
        self.assertEqual(model.hotkey('F11'),(0,122))

    def test_invalid_steps(self):
        for step in ({'type':'exec','value':'bad'}, {'type':'delay','seconds':float('nan')},
                     {'type':'keys','value':42},{'type':'keys','value':'__import__(os)'},
                     {'type':'key_down','value':'vk:999'}, {'type':'delay','seconds':-1},
                     {'type':'click','x':True,'y':0,'button':'left'}):
            with self.subTest(step=step),self.assertRaises(ValueError): model.validate_step(step)

    def test_failed_save_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.json'; path.write_text('original')
            with self.assertRaises(ValueError): model.save(path,[{'bad':'data'}])
            self.assertEqual(path.read_text(),'original')

    def test_limits(self):
        data=self.data(); data['scenarios'][0]['steps']=[{'type':'delay','seconds':600}]*7
        with self.assertRaises(ValueError): model.validate(data)

    def test_calls_reject_missing_targets_and_cycles(self):
        data=self.data()
        main=data['scenarios'][0]
        child=model.scenario('Подпрограмма')
        data['scenarios'].append(child)
        for target in ('missing',main['id'],child['id']):
            with self.subTest(target=target):
                main['steps']=[{'type':'call','scenario_id':target}]
                child['steps']=[{'type':'call','scenario_id':main['id']}] if target==child['id'] else []
                with self.assertRaisesRegex(ValueError,'отсутствующий|Циклический'): model.validate(data)

    def test_limits_include_each_invocation(self):
        data=self.data()
        main=data['scenarios'][0]
        child=model.scenario('Подпрограмма')
        data['scenarios'].append(child)
        call={'type':'call','scenario_id':child['id']}
        main['steps']=[call]*6
        child['steps']=[{'type':'delay','seconds':600}]
        self.assertIs(model.validate(data),data)
        main['steps'].append(call)
        with self.assertRaisesRegex(ValueError,'ожиданий'): model.validate(data)
        main['steps']=[call]*2
        child['steps']=[{'type':'keys','value':'z'}]*5000
        with self.assertRaisesRegex(ValueError,'шагов с учётом вызовов'): model.validate(data)
