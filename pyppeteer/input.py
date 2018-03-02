#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Keyboard and Mouse module."""

import asyncio
from typing import Any, Dict, TYPE_CHECKING

from pyppeteer.connection import Session
from pyppeteer.errors import PyppeteerError
from pyppeteer.us_keyboard_layout import keyDefinitions

if TYPE_CHECKING:
    from typing import Set  # noqa: F401


class Keyboard(object):
    """Keyboard class."""

    def __init__(self, client: Session) -> None:
        """Make new keyboard object."""
        self._client = client
        self._modifiers = 0
        self._pressedKeys: Set[str] = set()

    async def down(self, key: str, options: dict = None, **kwargs: Any
                   ) -> None:
        """Press key down."""
        options = options or dict()
        options.update(kwargs)

        description = self._keyDescriptionForString(key)
        autoRepeat = description['key'] in self._pressedKeys
        self._pressedKeys.add(description['code'])
        self._modifiers |= self._modifierBit(description['key'])

        text = options.get('text')
        if text is None:
            text = description['text']

        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'keyDown' if text else 'rawKeyDown',
            'modifiers': self._modifiers,
            'windowsVirtualKeyCode': description['keyCode'],
            'code': description['code'],
            'key': description['key'],
            'text': text,
            'unmodifiedText': text,
            'autoRepeat': autoRepeat,
            'location': description['location'],
            'isKeypad': description['location'] == 3,
        })

    def _modifierBit(self, key: str) -> int:
        if key == 'Alt':
            return 1
        if key == 'Control':
            return 2
        if key == 'Meta':
            return 4
        if key == 'Shift':
            return 8
        return 0

    def _keyDescriptionForString(self, keyString: str) -> Dict:  # noqa: C901
        shift = self._modifiers & 8
        description = {
            'key': '',
            'keyCode': 0,
            'code': '',
            'text': '',
            'location': 0,
        }

        definition: Dict = keyDefinitions.get(keyString)  # type: ignore
        if not definition:
            raise PyppeteerError(f'Unknown key: {keyString}')

        if 'key' in definition:
            description['key'] = definition['key']
        if shift and definition.get('shiftKey'):
            description['key'] = definition['shiftKey']

        if 'keyCode' in definition:
            description['keyCode'] = definition['keyCode']
        if shift and definition.get('shiftKeyCode'):
            description['keyCode'] = definition['shiftKeyCode']

        if 'code' in definition:
            description['code'] = definition['code']

        if 'location' in definition:
            description['location'] = definition['location']

        if len(description['key']) == 1:  # type: ignore
            description['text'] = description['key']

        if 'text' in definition:
            description['text'] = definition['text']
        if shift and definition.get('shiftText'):
            description['text'] = definition['shiftText']

        if self._modifiers & ~8:
            description['text'] = ''

        return description

    async def up(self, key: str) -> None:
        """Up pressed key."""
        description = self._keyDescriptionForString(key)

        self._modifiers &= ~self._modifierBit(description['key'])
        self._pressedKeys.remove(description['code'])
        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'keyUp',
            'modifiers': self._modifiers,
            'key': description['key'],
            'windowsVirtualKeyCode': description['keyCode'],
            'code': description['code'],
            'location': description['location'],
        })

    async def sendCharacter(self, char: str) -> None:
        """Send character."""
        await self._client.send('Input.dispatchKeyEvent', {
            'type': 'char',
            'modifiers': self._modifiers,
            'text': char,
            'key': char,
            'unmodifiedText': char,
        })

    async def type(self, text: str, options: Dict = None, **kwargs: Any
                   ) -> None:
        """Type characters."""
        options = options or dict()
        options.update(kwargs)

        delay = 0
        if options and options.get('delay'):
            delay = options['delay']
        for char in text:
            if 'char' in keyDefinitions:
                await self.press(char, {'delay': delay})
            else:
                await self.sendCharacter(char)
            if delay:
                await asyncio.sleep(delay / 1000)

    async def press(self, key: str, options: Dict = None, **kwargs: Any
                    ) -> None:
        """Press key."""
        options = options or dict()
        options.update(kwargs)

        await self.down(key, options)
        if options and options.get('delay'):
            await asyncio.sleep(options['delay'] / 1000)
        await self.up(key)


class Mouse(object):
    """Mouse class."""

    def __init__(self, client: Session, keyboard: Keyboard) -> None:
        """Make new mouse object."""
        self._client = client
        self._keyboard = keyboard
        self._x = 0.0
        self._y = 0.0
        self._button = 'none'

    async def move(self, x: float, y: float, options: dict = None,
                   **kwargs: Any) -> None:
        """Move cursor."""
        options = options or dict()
        options.update(kwargs)
        fromX = self._x
        fromY = self._y
        self._x = x
        self._y = y
        steps = options.get('steps', 1)
        for i in range(1, steps + 1):
            x = round(fromX + (self._x - fromX) * (i / steps))
            y = round(fromY + (self._y - fromY) * (i / steps))
            await self._client.send('Input.dispatchMouseEvent', {
                'type': 'mouseMoved',
                'button': self._button,
                'x': x,
                'y': y,
                'modifiers': self._keyboard._modifiers,
            })

    async def click(self, x: float, y: float, options: dict = None,
                    **kwargs: Any) -> None:
        """Click button at (x, y)."""
        if options is None:
            options = dict()
        options.update(kwargs)
        await self.move(x, y)
        await self.down(options)
        if options and options.get('delay'):
            await asyncio.sleep(options.get('delay', 0))
        await self.up(options)

    async def down(self, options: dict = None, **kwargs: Any) -> None:
        """Press down button."""
        if options is None:
            options = dict()
        options.update(kwargs)
        self._button = options.get('button', 'left')
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mousePressed',
            'button': self._button,
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
        })

    async def up(self, options: dict = None, **kwargs: Any) -> None:
        """Up pressed button."""
        if options is None:
            options = dict()
        options.update(kwargs)
        self._button = 'none'
        await self._client.send('Input.dispatchMouseEvent', {
            'type': 'mouseReleased',
            'button': options.get('button', 'left'),
            'x': self._x,
            'y': self._y,
            'modifiers': self._keyboard._modifiers,
            'clickCount': options.get('clickCount') or 1,
        })


class Touchscreen(object):
    """Touchscreen class."""

    def __init__(self, client: Session, keyboard: Keyboard) -> None:
        """Make new touchscreen object."""
        self._client = client
        self._keyboard = keyboard

    async def tap(self, x: float, y: float) -> None:
        """Tap (x, y)."""
        touchPoints = [{'x': round(x), 'y': round(y)}]
        await self._client.send('Input.dispatchTouchEvent', {
            'type': 'touchStart',
            'touchPoints': touchPoints,
            'modifiers': self._keyboard._modifiers,
        })
        await self._client.send('Input.dispatchTouchEvent', {
            'type': 'touchEnd',
            'touchPoints': [],
            'modifiers': self._keyboard._modifiers,
        })
