"""Strict, data-only scenario format. No executable expressions."""
import json
import math
import re
import uuid
DEFAULT_SETTINGS = {'start_delay': 0, 'record_delay': 3, 'control_bind': 'F12', 'theme': 'pink'}

KINDS = {'keys', 'delay', 'wait_click', 'wait_key', 'click', 'move', 'scroll',
         'key_down', 'key_up', 'mouse_down', 'mouse_up'}
SPECIAL = {'enter', 'tab', 'space', 'esc', 'backspace', 'delete', 'insert',
           'home', 'end', 'page_up', 'page_down', 'up', 'down', 'left', 'right',
           'ctrl', 'shift', 'alt', 'ctrl_l', 'ctrl_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r'}


def key_valid(key):
    return isinstance(key, str) and (key in SPECIAL or bool(re.fullmatch(r'f(?:[1-9]|1[0-2])|vk:[0-9]{1,3}|[a-z0-9]', key))) and (not key.startswith('vk:') or 0 <= int(key[3:]) <= 255)


def simple_vk(value):
    if value.startswith('vk:'): return int(value[3:])
    if len(value)==1: return ord(value.upper())
    if re.fullmatch(r'f(?:[1-9]|1[0-2])',value): return 111+int(value[1:])
    return None


def combo(text):
    if not isinstance(text, str) or len(text)>100:
        raise ValueError('Сочетание должно быть строкой длиной до 100 символов.')
    parts = text.lower().replace('control', 'ctrl').replace('escape', 'esc').replace(' ', '').split('+')
    if not 1 <= len(parts) <= 5 or len(set(parts)) != len(parts) or not all(key_valid(p) for p in parts):
        raise ValueError('Клавиши: латинские A–Z, 0–9, F1–F12, Enter, Ctrl+Shift+S и т. п.')
    return parts


def hotkey(text):
    parts = combo(text)
    modifiers = {'ctrl': 2, 'alt': 1, 'shift': 4}
    keys = [p for p in parts if p not in modifiers]
    if len(keys) != 1 or any(p not in modifiers for p in parts[:-1]):
        raise ValueError('Бинд: F6 либо Ctrl+Alt+K; основная клавиша — последняя.')
    key = keys[0]
    if not re.fullmatch(r'f(?:[1-9]|1[0-2])|[a-z0-9]', key):
        raise ValueError('Основная клавиша бинда: A–Z, 0–9 или F1–F12.')
    if len(parts) == 1 and not key.startswith('f'):
        raise ValueError('Для буквы или цифры добавь Ctrl/Alt/Shift.')
    return sum(modifiers[p] for p in parts[:-1]), int(key[1:]) + 111 if key.startswith('f') else ord(key.upper())


def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Число должно быть от {low} до {high}.')


def validate_step(step):
    if not isinstance(step, dict) or step.get('type') not in KINDS:
        raise ValueError('Неизвестный тип шага.')
    kind = step['type']
    if kind == 'keys': combo(step.get('value', ''))
    if kind in ('key_down', 'key_up', 'wait_key') and not key_valid(step.get('value')):
        raise ValueError('Укажи одну клавишу: space, enter, z, F1–F12 и т. п.')
    if kind in ('delay', 'wait_click', 'wait_key'): number(step.get('seconds'), 0.01, 600)
    if kind in ('click', 'move', 'mouse_down', 'mouse_up'):
        for axis in ('x', 'y'):
            number(step.get(axis), -100000, 100000)
            if type(step[axis]) is not int: raise ValueError('Координаты должны быть целыми.')
    if kind in ('click', 'mouse_down', 'mouse_up') and step.get('button') not in ('left', 'right', 'middle'):
        raise ValueError('Неизвестная кнопка мыши.')
    if kind == 'scroll':
        for axis in ('dx', 'dy'):
            number(step.get(axis), -100, 100)
            if type(step[axis]) is not int: raise ValueError('Прокрутка должна быть целой.')
    return step


def scenario(name='Новая магия', bind=''):
    return {'id': uuid.uuid4().hex, 'name': name, 'bind': bind, 'steps': []}


def validate(data):
    if not isinstance(data, dict) or type(data.get('format')) is not int or data.get('format') != 1 or not isinstance(data.get('scenarios'), list) or len(data['scenarios']) > 100:
        raise ValueError('Ожидается файл Lisa Macro Magic формата 1, до 100 сценариев.')
    settings = settings_for(data)
    ids, binds = set(), {hotkey(settings['control_bind'])}
    total = 0
    for item in data['scenarios']:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'] or item['id'] in ids:
            raise ValueError('Некорректный или повторяющийся ID.')
        ids.add(item['id'])
        if not isinstance(item.get('name'), str) or not 1 <= len(item['name'].strip()) <= 100:
            raise ValueError('Название: от 1 до 100 символов.')
        if not isinstance(item.get('bind'), str): raise ValueError('Бинд должен быть строкой.')
        if item['bind']:
            normalized = hotkey(item['bind'])
            if normalized in binds: raise ValueError('Бинд совпадает с другим сценарием или управляющей клавишей.')
            binds.add(normalized)
        if not isinstance(item.get('steps'), list) or len(item['steps']) > 10000:
            raise ValueError('Не более 10000 шагов в сценарии.')
        seconds = 0
        for step in item['steps']:
            validate_step(step)
            seconds += step.get('seconds', 0) if step['type'] in ('delay', 'wait_click','wait_key') else 0
        if seconds > 3600: raise ValueError('Сумма ожиданий сценария — не более часа.')
        total += len(item['steps'])
    if total > 20000: raise ValueError('Не более 20000 шагов в файле.')
    for item in data['scenarios']:
        for step in item['steps']:
            if step['type']=='wait_key' and (0,simple_vk(step['value'])) in binds:
                raise ValueError('Клавиша ожидания занята управляющим биндом или запуском сценария. Выбери другую.')
    return data


def load(path):
    return load_project(path)['scenarios']


def settings_for(data):
    supplied=data.get('settings',{})
    if not isinstance(supplied,dict): raise ValueError('Настройки должны быть объектом JSON.')
    result={**DEFAULT_SETTINGS,**supplied}
    for key in ('start_delay','record_delay'):
        if type(result[key]) is not int or not (1 if key=='record_delay' else 0)<=result[key]<=60:
            raise ValueError('Задержка запуска: 0–60 с; подготовки записи: 1–60 с, целые числа.')
    if result['theme'] not in ('pink','dark'): raise ValueError('Неизвестная тема.')
    hotkey(result['control_bind'])
    return result


def load_project(path):
    if path.stat().st_size > 5_000_000: raise ValueError('Файл больше 5 МБ.')
    data=validate(json.loads(path.read_text(encoding='utf-8-sig')))
    data['settings']=settings_for(data)
    return data


def save(path, scenarios, settings=None):
    data = validate({'format': 1, 'scenarios': scenarios, 'settings': settings or dict(DEFAULT_SETTINGS)})
    # Atomic replacement in the user-selected directory.
    import os
    import tempfile
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, suffix='.tmp', delete=False) as f:
            name = f.name
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name): os.unlink(name)


def describe(step):
    kind = step['type']
    if kind == 'keys': return '⌨  ' + step['value']
    if kind == 'delay': return f"⏱  Пауза {step['seconds']:g} с"
    if kind == 'wait_click': return f"♡  Ждать ручной ЛКМ (до {step['seconds']:g} с)"
    if kind == 'wait_key': return f"♡  Ждать {step['value']} (до {step['seconds']:g} с)"
    if kind in ('key_down', 'key_up'): return f"⌨  {step['value']} {'↓' if kind == 'key_down' else '↑'}"
    if kind == 'scroll': return f"↕  Прокрутка {step['dx']}, {step['dy']}"
    return f"{'↗' if kind == 'move' else '🖱'}  {kind}: {step.get('button', '')} ({step['x']}, {step['y']})"
