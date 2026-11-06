import unittest
import types
from unittest.mock import MagicMock,patch
import hotkeys
import model


class HotkeyTests(unittest.TestCase):
    def test_dispatch_and_unregister(self):
        events=[]; listener=MagicMock(); listener.is_alive.return_value=True
        manager=hotkeys.Hotkeys(events.append)
        first=model.scenario('Первый','F6'); second=model.scenario('Второй','Ctrl+Alt+K')
        with patch('pynput.keyboard.Listener',return_value=listener): manager.configure([first,second])
        key=lambda vk:types.SimpleNamespace(vk=vk)
        manager.press(key(117)); manager.press(key(117)); manager.release(key(117))
        manager.press(key(123)); manager.release(key(123))
        manager.press(key(162)); manager.press(key(164)); manager.press(key(75))
        self.assertEqual(events,[first['id'],'control',second['id']])
        manager.clear(); listener.stop.assert_called_once()

    def test_reconfigure_control_and_ignore_repeat(self):
        events=[]; listener=MagicMock(); listener.is_alive.return_value=True
        manager=hotkeys.Hotkeys(events.append)
        with patch('pynput.keyboard.Listener',return_value=listener) as factory:
            manager.configure([],control_bind='F11')
            key=lambda vk:types.SimpleNamespace(vk=vk)
            manager.press(key(123)); self.assertEqual(events,[])
            manager.press(key(122)); manager.configure([],control_bind='F11'); manager.press(key(122))
            self.assertEqual(events,['control'])
            manager.release(key(122)); manager.press(key(122)); self.assertEqual(events,['control','control'])
            self.assertEqual(factory.call_count,1)
            self.assertFalse(factory.call_args.kwargs['suppress'])
            self.assertFalse(factory.call_args.kwargs['win32_event_filter'](0,types.SimpleNamespace(flags=0x10)))
        manager.clear()

    def test_only_matched_shortcut_is_suppressed(self):
        events=[]; listener=MagicMock(); listener.is_alive.return_value=True
        manager=hotkeys.Hotkeys(events.append)
        with patch('pynput.keyboard.Listener',return_value=listener): manager.configure([])
        event=lambda vk,flags=0:types.SimpleNamespace(vkCode=vk,flags=flags)
        manager.filter(0x100,event(65)); manager.filter(0x101,event(65))
        listener.suppress_event.assert_not_called()
        manager.filter(0x100,event(123)); manager.filter(0x100,event(123)); manager.filter(0x101,event(123))
        self.assertEqual(events,['control']); self.assertEqual(listener.suppress_event.call_count,3)
        manager.filter(0x100,event(123,0x10)); self.assertEqual(events,['control'])
        manager.clear()
