"""Match configured shortcuts only; never store keyboard text."""
import threading
from model import hotkey


def key_vk(key):
    return getattr(key,'vkCode',None) or getattr(key,'vk',None) or getattr(getattr(key,'value',None),'vk',None)


def modifier_mask(down):
    return (2 if down.intersection({17,162,163}) else 0) | (1 if down.intersection({18,164,165}) else 0) | (4 if down.intersection({16,160,161}) else 0)


class Hotkeys:
    def __init__(self, callback):
        self.callback=callback
        self.listener=None
        self.lock=threading.Lock()
        self.matches=[]
        self.down=set()
        self.tracked=set()
        self.suppressed=set()

    def clear(self):
        listener,self.listener=self.listener,None
        if listener:
            listener.stop()
            if listener.is_alive():
                try: listener.join(timeout=1)
                except Exception: pass
        with self.lock:
            self.matches=[]; self.down.clear(); self.suppressed.clear()

    def configure(self,scenarios,control_bind='F12'):
        from pynput import keyboard
        bindings=[(control_bind,'control')]+[(s['bind'],s['id']) for s in scenarios if s['bind']]
        matches=[(*hotkey(bind),action) for bind,action in bindings]
        with self.lock:
            self.matches=matches
            self.tracked={vk for mods,vk,action in matches}|{16,17,18,160,161,162,163,164,165}
        if self.listener is None:
            listener=keyboard.Listener(suppress=False,win32_event_filter=self.filter)
            self.listener=listener
            try:
                listener.start(); listener.wait()
                if not listener.is_alive(): raise RuntimeError('Обработчик горячих клавиш недоступен.')
            except Exception:
                self.clear(); raise
        return []

    def press(self,key):
        vk=key_vk(key)
        action=None
        with self.lock:
            if vk not in self.tracked or vk in self.down: return
            self.down.add(vk)
            mask=modifier_mask(self.down)
            action=next((action for mods,base,action in self.matches if base==vk and mods==mask),None)
        if action: self.callback(action)
        return bool(action)

    def release(self,key):
        with self.lock:
            self.down.discard(key_vk(key))

    def filter(self,msg,data):
        # Injected macro events must never re-trigger shortcuts.
        if data.flags & 0x10: return False
        vk=data.vkCode
        if msg in (0x100,0x104):
            matched=self.press(data)
            if matched: self.suppressed.add(vk)
            suppress=vk in self.suppressed
        elif msg in (0x101,0x105):
            self.release(data)
            suppress=vk in self.suppressed; self.suppressed.discard(vk)
        else: suppress=False
        if suppress and self.listener: self.listener.suppress_event()
        # False hides the event from pynput callbacks, not from the other apps.
        return False
