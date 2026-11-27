"""Cancellable input engine. Hooks exist only during an explicit recording/wait."""
import ctypes
from ctypes import wintypes
import threading
import time
import os
from model import combo, describe, WAIT_STEPS, REPEAT_SOURCES, KEEP_REPEAT_SOURCE, REPEAT_ERROR

FOCUS_GRACE_SECONDS = 0.3


def foreground():
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    hwnd = user.GetForegroundWindow()
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value


class Cancelled(Exception): pass


def key_is_down(vk):
    return bool(vk is not None and ctypes.windll.user32.GetAsyncKeyState(vk)&0x8000)


class Player:
    def __init__(self, steps, status, finished, backend=None, focus=foreground, stop_label='F12',
                 trigger_modifiers=0, allowed_windows=(), input_lock=None, scenarios=None):
        self.steps, self.status, self.finished = steps, status, finished
        self.scenarios = scenarios if scenarios is not None else {}
        self.cancel = threading.Event()
        self.focus = focus
        self.backend = backend
        self.target = None
        self.keys, self.buttons = [], []
        self.stop_label=stop_label
        self.trigger_modifiers=trigger_modifiers
        self.allowed_windows=frozenset(allowed_windows)
        self.input_lock = input_lock if input_lock is not None else threading.Lock()
        self.owns_input = False
        self.step_location = ''

    def stop(self): self.cancel.set()

    def has_focus(self):
        return self.target is None or self.focus()[0] == self.target

    def check(self):
        if self.cancel.is_set(): raise Cancelled()
        if self.has_focus(): return
        deadline = time.monotonic() + FOCUS_GRACE_SECONDS
        while not self.has_focus():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('Активное окно сменилось. Запуск остановлен; выбери нужное окно и запусти заново.')
            if self.cancel.wait(min(0.02, remaining)): raise Cancelled()

    def acquire_input(self):
        while not self.input_lock.acquire(timeout=0.02):
            self.check()
        self.owns_input = True

    def release_input(self):
        self.input_lock.release()
        self.owns_input = False

    def release_held(self, keep_keys=(), keep_buttons=()):
        error = None
        for held, keep, controller in ((self.keys, keep_keys, self.backend[2]),
                                       (self.buttons, keep_buttons, self.backend[3])):
            for value in reversed(held.copy()):
                if value in keep: continue
                try: controller.release(value)
                except Exception as exc: error = exc
                else: held.remove(value)
        return error

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.cancel.wait(min(0.02, max(0, end - time.monotonic())))
        self.check()

    def resolve(self, value):
        keyboard = self.backend[0]
        if value.startswith('vk:'): return keyboard.KeyCode.from_vk(int(value[3:]))
        # Macro letters denote Windows keys, not text to be entered. Sending a
        # character lets pynput consult the current layout or fall back to
        # Unicode input, which is not an S-key shortcut on a Russian layout.
        if len(value)==1 and ('a'<=value<='z' or '0'<=value<='9'):
            return keyboard.KeyCode.from_vk(ord(value.upper()))
        return getattr(keyboard.Key, value, value)

    def key_down(self, value):
        key = self.resolve(value)
        if key not in self.keys: self.keys.append(key)
        self.backend[2].press(key)

    def key_up(self, value):
        key = self.resolve(value)
        self.backend[2].release(key)
        if key in self.keys: self.keys.remove(key)

    def mouse_down(self, step, move=True):
        button = getattr(self.backend[1].Button, step['button'])
        if move: self.backend[3].position = (step['x'], step['y'])
        if button not in self.buttons: self.buttons.append(button)
        self.backend[3].press(button)

    def mouse_up(self, step, move=True):
        button = getattr(self.backend[1].Button, step['button'])
        if move: self.backend[3].position = (step['x'], step['y'])
        self.backend[3].release(button)
        if button in self.buttons: self.buttons.remove(button)

    def wait_click(self, seconds):
        # Complete on release, so the physical button is up before the next key.
        mouse = self.backend[1]
        event = threading.Event()
        position = None
        completed = None
        def click(x, y, button, down):
            nonlocal position, completed
            if button != mouse.Button.left or event.is_set(): return
            focused = self.has_focus()
            if down:
                position = (x, y) if focused else None
            else:
                if position is not None and focused:
                    completed = {'type':'click', 'button':'left', 'x':position[0], 'y':position[1]}
                    event.set()
                position = None
        def physical(msg, data):
            return not (data.flags & 1)  # LLMHF_INJECTED
        listener = mouse.Listener(on_click=click, suppress=False, win32_event_filter=physical)
        listener.start()
        try:
            listener.wait()
            deadline = time.monotonic() + seconds
            while not event.is_set():
                self.check()
                if time.monotonic() >= deadline: raise RuntimeError('Время ожидания ручного клика истекло.')
                event.wait(0.02)
            self.check()
            self.wait(0.12)
            return completed
        finally:
            listener.stop()
            listener.join(timeout=1)

    def wait_key(self,value,seconds):
        from hotkeys import key_vk
        keyboard=self.backend[0]
        expected=self.resolve(value)
        expected_vk=key_vk(expected)
        event=threading.Event(); pressed=threading.Event()
        ready=threading.Event()
        if not key_is_down(expected_vk): ready.set()
        def matches(key):
            actual=key_vk(key)
            generic={17:{17,162,163},16:{16,160,161},18:{18,164,165}}
            if expected_vk in generic: return actual in generic[expected_vk]
            return actual==expected_vk if actual is not None and expected_vk is not None else key==expected
        def down(key):
            if matches(key) and ready.is_set() and self.has_focus(): pressed.set()
        def up(key):
            if matches(key):
                if not ready.is_set(): ready.set(); return
                if pressed.is_set() and self.has_focus(): event.set()
                pressed.clear()
        listener=keyboard.Listener(on_press=down,on_release=up,suppress=False,
            win32_event_filter=lambda msg,data:not(data.flags & 0x10))
        listener.start()
        try:
            listener.wait()
            deadline=time.monotonic()+seconds
            while not event.is_set():
                self.check()
                if time.monotonic()>=deadline: raise RuntimeError(f'Время ожидания клавиши {value} истекло.')
                event.wait(.02)
            self.check(); self.wait(.12)
        finally:
            listener.stop(); listener.join(timeout=1)

    def execute(self, step):
        kind = step['type']
        if kind == 'delay': self.wait(step['seconds'])
        elif kind == 'wait_click': return self.wait_click(step['seconds'])
        elif kind == 'wait_key': self.wait_key(step['value'],step['seconds'])
        elif kind == 'keys':
            parts = combo(step['value'])
            for value in parts:
                self.check()
                self.key_down(value)
                self.wait(0.025)
            for value in reversed(parts): self.key_up(value)
        elif kind == 'key_down': self.key_down(step['value'])
        elif kind == 'key_up': self.key_up(step['value'])
        elif kind == 'move': self.backend[3].position = (step['x'], step['y'])
        elif kind == 'mouse_down': self.mouse_down(step)
        elif kind == 'mouse_up': self.mouse_up(step)
        elif kind in ('click', 'click_here'):
            move = kind == 'click'
            if not move:
                x, y = self.backend[3].position
                step = {'type':'click', 'button':step['button'], 'x':x, 'y':y}
            self.mouse_down(step, move=move)
            self.wait(0.04)
            self.mouse_up(step, move=move)
            return step
        elif kind == 'scroll': self.backend[3].scroll(step['dx'], step['dy'])

    def play_steps(self, steps, path=''):
        previous = None
        for number, step in enumerate(steps, 1):
            location = f'{path}{number}/{len(steps)}'
            self.step_location = location
            self.check()
            kind = step['type']
            if kind == 'repeat' and previous is None: raise ValueError(REPEAT_ERROR)

            # Other players can send input during a wait unless a key or button is held.
            if kind in WAIT_STEPS and self.owns_input and not (self.keys or self.buttons):
                self.release_input()
            called = self.scenarios.get(step['scenario_id']) if kind == 'call' else None
            if kind == 'call' and called is None:
                raise ValueError('Сценарий для выполнения отсутствует.')
            text = describe(step, called['name'] if called is not None else None)
            self.status(f'Шаг {location} · {text} · {self.stop_label} — стоп')
            if called is not None:
                keep_keys, keep_buttons = tuple(self.keys), tuple(self.buttons)
                self.play_steps(called['steps'], f"{location} → «{called['name']}» ")
                error = self.release_held(keep_keys, keep_buttons)
                if error is not None: raise error
                self.step_location = location
                previous = None
            else:
                if kind not in WAIT_STEPS and not self.owns_input: self.acquire_input()
                self.check()
                performed = self.execute(previous if kind == 'repeat' else step)
                if kind not in KEEP_REPEAT_SOURCE:
                    previous = (performed or step) if kind in REPEAT_SOURCES else None
            self.wait(0.01)

    def run(self, countdown=3):
        message = 'Готово ♡'
        self.step_location = ''
        try:
            if self.backend is None:
                from pynput import keyboard, mouse
                self.backend = (keyboard, mouse, keyboard.Controller(), mouse.Controller())
            for second in range(countdown, 0, -1):
                self.status(f'Старт через {second}… переключись в нужное окно. {self.stop_label} — стоп')
                self.wait(1)
            if self.trigger_modifiers:
                deadline=time.monotonic()+3
                modifiers=[vk for bit,vk in [(2,17),(1,18),(4,16)] if self.trigger_modifiers & bit]
                while any(ctypes.windll.user32.GetAsyncKeyState(vk)&0x8000 for vk in modifiers):
                    if time.monotonic()>deadline: raise RuntimeError('Отпусти модификаторы бинда и запусти заново.')
                    self.wait(.01)
            hwnd, pid = self.focus()
            if not hwnd or (pid == os.getpid() and hwnd not in self.allowed_windows):
                raise RuntimeError('Выбрано окно редактора. При задержке 0 запускай биндом из браузера; для кнопки задай задержку и переключись в целевое окно.')
            self.target = hwnd
            self.play_steps(self.steps)
        except Cancelled:
            message = 'Остановлено. Все нажатые приложением клавиши отпущены.'
        except Exception as exc:
            where = f' на шаге {self.step_location}' if self.step_location else ''
            message = f'Ошибка{where}: {exc}'
        finally:
            if self.backend: self.release_held()
            if self.owns_input: self.release_input()
            self.finished(message)


class Recorder:
    def __init__(self, stop_requested, focus=foreground, control_signature=(0,123),allowed_windows=()):
        self.stop_requested, self.focus = stop_requested, focus
        self.lock = threading.Lock()
        self.steps = []
        self.listeners = []
        self.active = False
        self.target = None
        self.previous = self.started = 0
        self.last_move = 0
        self.control_signature=control_signature
        self.down=set()
        self.ignored=set()
        self.allowed_windows=frozenset(allowed_windows)

    def add(self, step):
        with self.lock:
            if not self.active: return
            if self.focus()[0] != self.target:
                self.active = False
                self.stop_requested('Запись остановлена: активное окно сменилось.')
                return
            now = time.monotonic()
            if now - self.started > 600 or len(self.steps) >= 9990:
                self.active = False
                self.stop_requested('Достигнут предел записи: 10 минут или 10000 шагов.')
                return
            elapsed = now - self.previous
            if elapsed >= 0.01: self.steps.append({'type': 'delay', 'seconds': round(elapsed, 3)})
            self.steps.append(step)
            self.previous = now

    @staticmethod
    def key_value(key):
        from pynput import keyboard
        from model import key_valid
        if isinstance(key, keyboard.Key): value = key.name
        elif key.vk is not None: value = f'vk:{key.vk}'
        else: value = (key.char or '').lower()
        return value if key_valid(value) else None

    def key_event(self, key, down):
        from hotkeys import key_vk,modifier_mask
        vk=key_vk(key)
        if down:
            self.down.add(vk)
            if self.control_signature==(modifier_mask(self.down),vk):
                self.ignored.add(vk); return
        else:
            self.down.discard(vk)
            if vk in self.ignored: self.ignored.discard(vk); return
        value = self.key_value(key)
        if value: self.add({'type': 'key_down' if down else 'key_up', 'value': value})

    def move(self, x, y):
        now = time.monotonic()
        if now - self.last_move >= 0.08:
            self.last_move = now
            self.add({'type': 'move', 'x': x, 'y': y})

    def click(self, x, y, button, down):
        if button.name in ('left', 'right', 'middle'):
            self.add({'type': 'mouse_down' if down else 'mouse_up', 'button': button.name, 'x': x, 'y': y})

    def start(self):
        from pynput import keyboard, mouse
        hwnd, pid = self.focus()
        if not hwnd or (pid == os.getpid() and hwnd not in self.allowed_windows): raise RuntimeError('Переключись в браузер или Input Monitor до окончания отсчёта.')
        self.target = hwnd
        self.previous = self.started = time.monotonic()
        self.active = True
        self.listeners = [
            keyboard.Listener(on_press=lambda k: self.key_event(k, True), on_release=lambda k: self.key_event(k, False),
                              suppress=False, win32_event_filter=lambda msg, data: not (data.flags & 0x10)),
            mouse.Listener(on_move=self.move, on_click=self.click,
                           on_scroll=lambda x,y,dx,dy: self.add({'type':'scroll','dx':dx,'dy':dy}),
                           suppress=False, win32_event_filter=lambda msg, data: not (data.flags & 1))]
        try:
            for listener in self.listeners:
                listener.start()
                listener.wait()
        except Exception:
            self.stop()
            raise

    def stop(self):
        with self.lock: self.active = False
        for listener in self.listeners: listener.stop()
        for listener in self.listeners:
            if listener.is_alive():
                try: listener.join(timeout=1)
                except Exception: pass
        with self.lock: return list(self.steps)
