import types
import unittest
from unittest.mock import patch
import engine


class Controller:
    def __init__(self): self.events=[]; self.position=(0,0); self.on_press=None
    def press(self,key):
        self.events.append(('down',key))
        if self.on_press: self.on_press()
    def release(self,key): self.events.append(('up',key))
    def scroll(self,x,y): self.events.append(('scroll',x,y))


def backend():
    key=types.SimpleNamespace(Key=types.SimpleNamespace(ctrl='ctrl',shift='shift',enter='enter'),
                              KeyCode=types.SimpleNamespace(from_vk=lambda vk:vk))
    mouse=types.SimpleNamespace(Button=types.SimpleNamespace(left='left',right='right',middle='middle'))
    return key,mouse,Controller(),Controller()


class PlayerTests(unittest.TestCase):
    def player(self,steps):
        self.messages=[]; self.finished=[]; self.devices=backend()
        return engine.Player(steps,self.messages.append,self.finished.append,self.devices,focus=lambda:(101,999999))

    def test_shortcut_order_and_release(self):
        player=self.player([{'type':'keys','value':'ctrl+shift+s'}]); player.run(countdown=0)
        self.assertEqual(self.devices[2].events,[('down','ctrl'),('down','shift'),('down',83),('up',83),('up','shift'),('up','ctrl')])
        self.assertEqual(self.finished,['Готово ♡'])

    def test_emergency_stop_releases_held_key(self):
        player=self.player([{'type':'keys','value':'ctrl+s'},{'type':'keys','value':'z'}])
        self.devices[2].on_press=player.stop
        player.run(countdown=0)
        self.assertEqual(self.devices[2].events,[('down','ctrl'),('up','ctrl')])
        self.assertIn('Остановлено',self.finished[0])

    def test_focus_change_stops_before_next_step(self):
        player=self.player([{'type':'key_down','value':'ctrl'},{'type':'keys','value':'z'}])
        self.devices[2].on_press=lambda:setattr(player,'focus',lambda:(202,999999))
        player.run(countdown=0)
        self.assertEqual(self.devices[2].events,[('down','ctrl'),('up','ctrl')])
        self.assertIn('окно сменилось',self.finished[0])

    def test_mouse_release_after_error(self):
        player=self.player([{'type':'mouse_down','button':'left','x':10,'y':20}, {'type':'keys','value':'s'}])
        self.devices[3].on_press=lambda:(_ for _ in ()).throw(RuntimeError('test failure'))
        player.run(countdown=0)
        self.assertEqual(self.devices[3].events,[('down','left'),('up','left')])

    def test_wait_cancel_is_prompt(self):
        player=self.player([{'type':'delay','seconds':600}]); player.stop(); player.run(countdown=0)
        self.assertIn('Остановлено',self.finished[0])

    def test_own_window_is_rejected(self):
        player=self.player([{'type':'keys','value':'z'}]); player.focus=lambda:(1,engine.os.getpid())
        player.run(countdown=0)
        self.assertFalse(self.devices[2].events)

    def test_explicit_input_monitor_window_is_allowed_in_same_process(self):
        player=self.player([{'type':'keys','value':'z'}])
        player.focus=lambda:(42,engine.os.getpid()); player.allowed_windows=frozenset({42})
        player.run(countdown=0)
        self.assertEqual(self.devices[2].events,[('down',90),('up',90)])
        self.assertEqual(self.finished,['Готово ♡'])

    def test_permission_for_monitor_does_not_allow_editor(self):
        player=self.player([{'type':'keys','value':'z'}])
        player.focus=lambda:(43,engine.os.getpid()); player.allowed_windows=frozenset({42})
        player.run(countdown=0)
        self.assertFalse(self.devices[2].events)

    def test_manual_click_waits_for_release_and_ignores_right(self):
        player=self.player([{'type':'wait_click','seconds':.1}])
        class Listener:
            def __init__(self,**kw): self.click=kw['on_click']; self.stopped=False
            def start(self):
                self.click(0,0,'right',True); self.click(0,0,'right',False)
                self.click(0,0,'left',True); self.click(0,0,'left',False)
            def wait(self): pass
            def stop(self): self.stopped=True
            def join(self,timeout): pass
        self.devices[1].Listener=Listener
        player.run(countdown=0)
        self.assertEqual(self.finished,['Готово ♡'])

    def test_manual_click_timeout_cleans_listener(self):
        player=self.player([{'type':'wait_click','seconds':.01}]); instances=[]
        class Listener:
            def __init__(self,**kw): self.stopped=False; instances.append(self)
            def start(self): pass
            def wait(self): pass
            def stop(self): self.stopped=True
            def join(self,timeout): pass
        self.devices[1].Listener=Listener; player.run(countdown=0)
        self.assertTrue(instances[0].stopped); self.assertIn('истекло',self.finished[0])


class RecorderTests(unittest.TestCase):
    def test_listener_lifecycle_and_physical_event_filters(self):
        instances=[]
        class Listener:
            def __init__(self,**kwargs): self.options=kwargs; self.running=False; instances.append(self)
            def start(self): self.running=True
            def wait(self): pass
            def is_alive(self): return self.running
            def stop(self): self.running=False
            def join(self,timeout): pass
        fake=types.SimpleNamespace(keyboard=types.SimpleNamespace(Listener=Listener),mouse=types.SimpleNamespace(Listener=Listener))
        recorder=engine.Recorder(lambda msg:None,focus=lambda:(101,999999))
        with patch.dict('sys.modules',{'pynput':fake}): recorder.start()
        self.assertEqual(len(instances),2)
        with patch.object(recorder,'key_value',return_value='vk:90'):
            instances[0].options['on_press'](object()); instances[0].options['on_release'](object())
        button=types.SimpleNamespace(name='left')
        instances[1].options['on_click'](100,200,button,True)
        instances[1].options['on_click'](100,200,button,False)
        events=recorder.stop()
        self.assertEqual([s['type'] for s in events if s['type']!='delay'],['key_down','key_up','mouse_down','mouse_up'])
        self.assertTrue(all(not i.running for i in instances))
        for listener,flag in zip(instances,[0x10,1]):
            self.assertFalse(listener.options['suppress'])
            self.assertFalse(listener.options['win32_event_filter'](0,types.SimpleNamespace(flags=flag)))
            self.assertTrue(listener.options['win32_event_filter'](0,types.SimpleNamespace(flags=0)))

    def test_focus_change_adds_no_event(self):
        messages=[]; recorder=engine.Recorder(messages.append,focus=lambda:(2,99999))
        recorder.active=True; recorder.target=1
        recorder.add({'type':'keys','value':'z'})
        self.assertFalse(recorder.steps); self.assertFalse(recorder.active); self.assertTrue(messages)

    def test_record_timing_and_stop(self):
        recorder=engine.Recorder(lambda m:None,focus=lambda:(1,99999))
        recorder.active=True; recorder.target=1; recorder.started=10; recorder.previous=10
        with patch('engine.time.monotonic',return_value=10.25): recorder.add({'type':'key_down','value':'vk:90'})
        self.assertEqual(recorder.stop(),[{'type':'delay','seconds':.25},{'type':'key_down','value':'vk:90'}])
        recorder.add({'type':'keys','value':'s'}); self.assertEqual(len(recorder.steps),2)
