import unittest
import string
from unittest.mock import patch
from pynput import keyboard,mouse
from engine import Player
from test_engine import backend


class LayoutTests(unittest.TestCase):
    def test_all_letters_and_digits_use_virtual_keys(self):
        player=Player([],lambda m:None,lambda m:None,backend())
        for value in string.ascii_lowercase+string.digits:
            with self.subTest(value=value): self.assertEqual(player.resolve(value),ord(value.upper()))

    def test_explicit_vk_and_special_keys_still_work(self):
        player=Player([],lambda m:None,lambda m:None,backend())
        self.assertEqual(player.resolve('vk:83'),83)
        self.assertEqual(player.resolve('enter'),'enter'); self.assertEqual(player.resolve('ctrl'),'ctrl')

    def test_windows_s_key_never_uses_layout_character_conversion(self):
        player=Player([],lambda m:None,lambda m:None,(keyboard,mouse,None,None))
        with patch('pynput.keyboard._win32.VkKeyScan',side_effect=AssertionError('Layout lookup must not be used')):
            key=player.resolve('s')
            self.assertEqual(key.vk,0x53); self.assertIsNone(key.char)
            down=key._parameters(True); up=key._parameters(False)
        self.assertEqual(down['wVk'],0x53); self.assertEqual(up['wVk'],0x53)
        self.assertFalse(down['dwFlags'] & 4); self.assertFalse(up['dwFlags'] & 4)

    def test_key_down_up_steps_use_matching_vk(self):
        devices=backend()
        player=Player([],lambda m:None,lambda m:None,devices)
        player.execute({'type':'key_down','value':'s'}); player.execute({'type':'key_up','value':'s'})
        self.assertEqual(devices[2].events,[('down',83),('up',83)])
