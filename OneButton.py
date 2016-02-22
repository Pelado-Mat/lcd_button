# Copyright (c) 2015 Matias Vidal - Matias Vidal - matiasv@gmail.com
# Author: Matias Vidal
# A port of Arduino's One Button Library to GPIO
# http://www.mathertel.de/Arduino/OneButtonLibrary.aspx
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import time
import Adafruit_GPIO.GPIO as GPIO

UNPRESSED = 0
CLICK = 2
DOUBLECLICK = 3
LONG_START = 4
LONG_END =5

class OneButton(object):
    """
    A Class representing one phisical Button
    """
    _debounceTicks = 100

    def __init__(self, gpio, pin, activeLow=True, clickTicks=600, pressTicks=1000, pullUp=True):
        self._pin = pin
        self._gpio = gpio
        self._activeLow = activeLow
        self._clickTicks = clickTicks
        self._pressTicks = pressTicks
        self._state = 0
        self._isLongPressed = False
        self._lastChangeTime = 0
        self._lastState = UNPRESSED
        self._startTime = 0

        # CallBackFunctions
        self._clickFunc = None
        self._doubleClickFunc = None
        self._longPressStartFunc = None
        self._longPressStopFunc = None
        self._duringLongPressFunc = None

        if activeLow:
            self._buttonReleased = GPIO.HIGH
            self._buttonPressed = GPIO.LOW
        else:
            self._buttonReleased = GPIO.LOW
            self._buttonPressed = GPIO.HIGH

        # init GPIO
        self._gpio.setup(pin, GPIO.IN, pull_up_down= GPIO.PUD_UP if pullUp else GPIO.PUD_OFF)

    def attachClick(self, newFunc):
        self._clickFunc = newFunc

    def attachDoubleClick(self, newFunc):
        self._doubleClickFunc =  newFunc

    def attachLongPressStart(self, newFunc):
        self._longPressStartFunc = newFunc

    def attachLongPressStop(self, newFunc):
        self._longPressStopFunc = newFunc

    def attachDuringLongPress(self, newFunc):
        self._duringLongPressFunc = newFunc

    def isLongPressed(self):
        return self._isLongPressed

    def tick(self):
        buttonLevel = self._gpio.input(self._pin)
        now = time.time()*1000

        if self._state == 0:
            if buttonLevel == self._buttonPressed:
                self._state = 1
                self._startTime = now

        elif self._state == 1:
            if buttonLevel == self._buttonReleased and (now - self._startTime) < self._debounceTicks:
                self._state = 0
            elif buttonLevel == self._buttonReleased:
                self._state = 2
            elif buttonLevel == self._buttonPressed and (now - self._startTime) > self._pressTicks:
                self._isLongPressed = True
                self._lastState = LONG_START
                self._lastChangeTime = time.time()
                if self._longPressStartFunc:
                    self._longPressStartFunc(self._pin)
                if self._duringLongPressFunc:
                    self._duringLongPressFunc(self._pin)
                self._state = 6

        elif self._state == 2:
            if (now - self._startTime) > self._clickTicks:
                self._lastState = CLICK
                self._lastChangeTime = time.time()
                if self._clickFunc:
                    self._clickFunc(self._pin)
                self._state = 0
            elif buttonLevel == self._buttonPressed:
                self._state = 3

        elif self._state == 3:
            if buttonLevel == self._buttonReleased:
                self._lastState = DOUBLECLICK
                self._lastChangeTime = time.time()
                if self._doubleClickFunc:
                    self._doubleClickFunc(self._pin)
                self._state = 0

        elif self._state == 6:
            if buttonLevel == self._buttonReleased:
                self._isLongPressed = False
                self._lastState = LONG_END
                self._lastChangeTime = time.time()
                if self._longPressStopFunc:
                    self._longPressStopFunc(self._pin)
                self._state = 0
            else:
                self._isLongPressed = True
                if self._duringLongPressFunc:
                    self._duringLongPressFunc(self._pin)
    @property
    def pin(self):
        return self._pin

    @property
    def lastState(self):
        return self._lastState

    @property
    def lastChangeTime(self):
        return self._lastChangeTime
