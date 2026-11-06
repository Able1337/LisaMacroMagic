import types
import unittest
from unittest.mock import patch
import engine,model
from test_engine import backend


class WaitKeyTests(unittest.TestCase):
    def make(self,events,held=False):
        self.done=[]; self.instances=[]; self.devices=backend()
        self.space=types.SimpleNamespace(vk=32); self.other=types.SimpleNamespace(vk=65)
        self.devices[0].Key.space=self.space
        owner=self
        class Listener:
            def __init__(self,**options): self.options=options; self.stopped=False; owner.instances.append(self)
            def start(self):
                for name,key in events: self.options[name](key)
            def wait(self): pass
            def stop(self): self.stopped=True
            def join(self,timeout): pass
        self.devices[0].Listener=Listener
        return engine.Player([{'type':'wait_key','value':'space','seconds':.01}],lambda m:None,self.done.append,self.devices,focus=lambda:(101,999999))

    def test_fresh_press_and_release(self):
        events=[]; player=self.make(events)
        events.extend([('on_release',self.space),('on_press',self.other),('on_release',self.other),('on_press',self.space),('on_release',self.space)])
        with patch('engine.key_is_down',return_value=False): player.run(countdown=0)
        self.assertEqual(self.done,['Готово ♡']); self.assertTrue(self.instances[0].stopped)
        self.assertFalse(self.instances[0].options['suppress'])
        self.assertFalse(self.instances[0].options['win32_event_filter'](0,types.SimpleNamespace(flags=0x10)))

    def test_press_without_release_times_out_and_cleans_up(self):
        events=[]; player=self.make(events); events.append(('on_press',self.space))
        with patch('engine.key_is_down',return_value=False): player.run(countdown=0)
        self.assertIn('истекло',self.done[0]); self.assertTrue(self.instances[0].stopped)

    def test_already_held_key_needs_a_new_click(self):
        events=[]; player=self.make(events)
        events.extend([('on_press',self.space),('on_release',self.space)])
        with patch('engine.key_is_down',return_value=True): player.run(countdown=0)
        self.assertIn('истекло',self.done[0])

    def test_held_key_then_new_press_works(self):
        events=[]; player=self.make(events)
        events.extend([('on_release',self.space),('on_press',self.space),('on_release',self.space)])
        with patch('engine.key_is_down',return_value=True): player.run(countdown=0)
        self.assertEqual(self.done,['Готово ♡'])

    def test_cancel_wait(self):
        player=self.make([]); self.instances=[]
        class Listener:
            def __init__(self,**kw): pass
            def start(self): player.stop()
            def wait(self): pass
            def stop(self): pass
            def join(self,timeout): pass
        self.devices[0].Listener=Listener
        with patch('engine.key_is_down',return_value=False): player.run(countdown=0)
        self.assertIn('Остановлено',self.done[0])

    def test_model_validation_and_control_conflict(self):
        step={'type':'wait_key','value':'space','seconds':120}
        self.assertEqual(model.validate_step(step),step)
        self.assertIn('space',model.describe(step))
        scenario=model.scenario(); scenario['steps']=[{'type':'wait_key','value':'f12','seconds':120}]
        with self.assertRaises(ValueError): model.validate({'format':1,'scenarios':[scenario]})
        with self.assertRaises(ValueError): model.validate_step({'type':'wait_key','value':'ctrl+s','seconds':120})
        scenario['steps'][0]['value']='f7'
        with self.assertRaises(ValueError): model.validate({'format':1,'scenarios':[scenario,model.scenario('Другой','F7')]})
