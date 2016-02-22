#!/usr/bin/env python
# This plugin sends data to I2C for LCD 16x2 char with PCF8574. Visit for more: www.pihrt.com/elektronika/258-moje-rapsberry-pi-i2c-lcd-16x2.
# This plugin required python pylcd2.py library


from threading import Thread
from Queue import Queue
from random import randint
import json
import time
import sys
import traceback

import web
import gv  # Get access to sip's settings
from urls import urls  # Get access to sip's URLs
from sip import template_render
from webpages import ProtectedPage
from helpers import uptime, get_ip, get_cpu_temp, get_rpi_revision, stop_stations, set_output
from blinker import signal
import pylcd2
import Adafruit_GPIO.GPIO as GPIO
import OneButton

# Add a new url to open the data entry page.
urls.extend(['/lcd-button', 'plugins.lcd_button.settings',
             '/lcd-buttonj', 'plugins.lcd_button.settings_json',
             '/ulcd-but', 'plugins.lcd_button.update'])

# Add this plugin to the home page plugins menu
gv.plugin_menu.append(['LCD-Button Settings', '/lcd-button'])

################################################################################
# Main function loop:                                                          #
################################################################################


class LCDSender(Thread):
    def __init__(self, queue):
        Thread.__init__(self)
        self.daemon = True
        self.status = ''
        self._m_queue = queue
        self._text_shift = 0
        self._lcd = None
        self._manual_mode = False
        self._sleep_time = 0
        self._but1 = None # Black
        self._but2 = None # Red

        self._params = self.get_lcd_parms()
        self._but1 = OneButton.OneButton(gv.scontrol.board_gpio, self._params['but1_pin'],
                                           activeLow = self._params['but1_NormalOpen']) # Black
        self._but2 = OneButton.OneButton(gv.scontrol.board_gpio, self._params['but2_pin'],
                                           activeLow = self._params['but2_NormalOpen']) # Red
        self._lcd = pylcd2.lcd(self._params['lcd_adress'], 1 if get_rpi_revision() >= 2 else 0)
        self._but1.attachClick(self._butClick)
        self._but2.attachClick(self._butClick)

        self.start()

    def _butClick(self,pin):
        if pin == self._but1.pin:
            if self._text_shift == 7:
                self._text_shift = 0
            else:
                self._text_shift += 1

    def add_status(self, msg):
        if self.status:
            self.status += '\n' + msg
        else:
            self.status = msg

    def update(self):
        self._sleep_time = 0

    def _sleep(self, secs):
        self._sleep_time = secs
        while self._sleep_time > 0:
            time.sleep(1)
            self._sleep_time -= 1

    def set_manual_mode(self):
        lcd = self._lcd
        lcd.lcd_clear()
        lcd.lcd_puts('{:^15}'.format("Activar Bomba Manualmente?"), 1)
        lcd.lcd_puts('   SI  Cancelar', 2)
        start_wait = time.time()
        while ((time.time() - start_wait ) < 10) or \
                (self._but2.lastState == OneButton.CLICK and (self._but2.lastChangeTime > start_wait)): # Wait 10 secs or cancel
            self._but1.tick()
            self._but2.tick()
            if self._but1.lastState == OneButton.CLICK and (self._but1.lastChangeTime > start_wait):
                self._manual_mode = True
                lcd.lcd_clear()
                lcd.lcd_puts('{:^15}'.format("Iniciando Bomba"), 1)
                lcd.lcd_puts('{:^15}'.format("Manualmente"), 2)
                time.sleep(2)
                stop_stations()
                gv.sd['mm'] = 0
                gv.sd['en'] = 0
                vals = [0] * len(gv.srvals)
                vals[gv.sd['mas'] - 1] = 1 # Start Pump
                gv.srvals = vals
                set_output()
                manual_master_start = time.time()
                # now we wait to cancel with other double press
                last_update = time.time()
                while True:
                    time.sleep(10/1000)
                    self._but1.tick()
                    self._but2.tick()
                    if (time.time() - last_update) > 5:
                        # Keep Forcing the current State!
                        gv.sd['mm'] = 0
                        gv.sd['en'] = 0
                        vals = [0] * len(gv.srvals)
                        vals[gv.sd['mas'] - 1] = 1
                        gv.scontrol.stations = vals
                        run_min = int((time.time() - manual_master_start)/60)
                        run_sec = int((time.time() - manual_master_start)%60)
                        lcd.lcd_clear()
                        lcd.lcd_puts('{:^15}'.format("Cancelar Bomba Manual?"), 1)
                        lcd.lcd_puts(' Cancel - {:^3}:{}'.format(run_min,run_sec), 2)
                        last_update = time.time()
                    if self._but1.lastState == OneButton.CLICK and self._but1.lastChangeTime > manual_master_start: # Cancel Manual Mode
                        lcd.lcd_clear()
                        lcd.lcd_puts('{:^15}'.format("Detentiendo Bomba"), 1)
                        lcd.lcd_puts('{:^15}'.format("Modo Automatico"), 2)
                        time.sleep(3)
                        stop_stations()
                        gv.srvals = [0] * len(gv.srvals)
                        set_output()
                        gv.sd['mm'] = 0
                        gv.sd['en'] = 1
                        break



    def run(self):
        time.sleep(randint(3, 10))  # Sleep some time to prevent printing before startup information
        print "LCD Button plugin is active"
        old_text_index = -1
        last_update  = 0
        self._params = self.get_lcd_parms()
        while True:
            try:
                now = time.time()
                if not self._params['use_lcd'] :                      # if LCD plugin is disable
                    self._sleep(5)
                    continue

                self._but1.tick()
                self._but2.tick()
                if self._but1.isLongPressed() and self._but2.isLongPressed() and self._params['enable_manual_master']: # Double push!
                    self.set_manual_mode()
                if (now - self._but1.lastChangeTime) > 60: # Return displaying the default
                    self._text_shift = 0
                if old_text_index != self._text_shift or self._m_queue.qsize() > 0 or (now - last_update) > 2 : #Update every 2 seconds
                    last_update = now
                    old_text_index = self._text_shift
                    self.get_LCD_print(self._text_shift)   # Print to LCD 16x2
                time.sleep(5/1000) # 5 ms

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_string = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                self.add_status('LCD-Button plugin encountered error: ' + err_string)
                self._sleep(60)

    def get_LCD_print(self, report):
        lcd = self._lcd
        if self._m_queue.qsize() > 0:
            lcd.lcd_clear()
            lcd.lcd_puts('{:^15}'.format("SIP - Messages"), 1)
            lcd.lcd_puts('{:^15}'.format(self._m_queue.get()), 2)
            self.add_status('SIP / new message')
            time.sleep(2)
        elif report == 0:
            lcd.lcd_clear()
            lcd.lcd_puts('{:^15}'.format("SIP - status"), 1)
            lcd.lcd_puts('{:^15}'.format(get_sip_status()), 2)
            self.add_status('SIP / Irrigation syst.')
        elif report == 1:
            lcd.lcd_clear()
            lcd.lcd_puts("Software SIP:", 1)
            lcd.lcd_puts(gv.ver_date, 2)
            self.add_status('Software SIP: / ' + gv.ver_date)
        elif report == 2:
            lcd.lcd_clear()
            ip = get_ip()
            lcd.lcd_puts("My IP is:", 1)
            lcd.lcd_puts(str(ip), 2)
            self.add_status('My IP is: / ' + str(ip))
        elif report == 3:
            lcd.lcd_clear()
            lcd.lcd_puts("Port IP:", 1)
            lcd.lcd_puts("8080", 2)
            self.add_status('Port IP: / 8080')
        elif report == 4:
            lcd.lcd_clear()
            temp = get_cpu_temp(gv.sd['tu']) + ' ' + gv.sd['tu']
            lcd.lcd_puts("CPU temperature:", 1)
            lcd.lcd_puts(temp, 2)
            self.add_status('CPU temperature: / ' + temp)
        elif report == 5:
            lcd.lcd_clear()
            da = time.strftime('%d.%m.%Y', time.gmtime(gv.now))
            ti = time.strftime('%H:%M:%S', time.gmtime(gv.now))
            lcd.lcd_puts(da, 1)
            lcd.lcd_puts(ti, 2)
            self.add_status(da + ' ' + ti)
        elif report == 6:
            lcd.lcd_clear()
            up = uptime()
            lcd.lcd_puts("System run time:", 1)
            lcd.lcd_puts(up, 2)
            self.add_status('System run time: / ' + up)
        elif report == 7:
            lcd.lcd_clear()
            if gv.sd['rs']:
                rain_sensor = "Active"
            else:
                rain_sensor = "Inactive"
            lcd.lcd_puts("Rain sensor:", 1)
            lcd.lcd_puts(rain_sensor, 2)
            self.add_status('Rain sensor: / ' + rain_sensor)

    def get_lcd_parms(self):
        """Returns the data form file."""
        datalcd = {
            'use_lcd': False,
            'enable_manual_master': False,
            'lcd_adress': 0x27,
            'status': self.status,
            'but1_pin': 40,           #Red Button
            'but1_NormalOpen': True,
            'but2_pin': 38,         #Black Button
            'but2_NormalOpen': False
        }
        try:
            with open('./data/lcd_button.json', 'r') as f:  # Read the settings from file
                file_data = json.load(f)
            for key, value in file_data.iteritems():
                if key in datalcd:
                    datalcd[key] = value
        except Exception:
            pass

        return datalcd

message_queue = Queue()
checker = LCDSender(message_queue)

def get_lcd_options():
    datalcd = checker.get_lcd_parms()
    options = [
            ["use_lcd",_("Enable the plugin"), "boolean", _("Enable the LCD and Button Plugin"), _("General"),datalcd['use_lcd']],
            ["enable_manual_master",_("Enable Master Mode"), "boolean", _("Enable manually starting the master station from the button and LCD menu"), _("General"),datalcd['enable_manual_master']],
            ["lcd_adress", _("i2c Address of the LCD"),"hex",_("i2c Address of the LCD"),_("LCD"),datalcd['lcd_adress']],
            ["but1_pin", _("Button 1 PIN"),"int",_("Button 1 PIN"),_("Buttons"),datalcd['but1_pin']],
            ["but1_NormalOpen", _("Button 1 is Normal Open"),"boolean",_("Button 1 is Normal Open"),_("Buttons"),datalcd['but1_NormalOpen']],
            ["but2_pin", _("Button 2 PIN"),"int",_("Button 2 GPIO"),_("Buttons"),datalcd['but2_pin']],
            ["but2_NormalOpen", _("Button 2 is Normal Open"),"boolean",_("Button 2 is Normal Open"),_("Buttons"),datalcd['but2_NormalOpen']]
        ]
    return options


# Connect to the signals
def notify_zone_change(name, **kw):
    pon = gv.pon
    if pon == 98:
        pgr = get_sip_status('Run-once - ')
        message_queue.put(pgr)
    elif pon == 99:
        pgr = get_sip_status('Manual - ')
        message_queue.put(pgr)
    elif pon is None:
        pass
    else:
        p = {}
        for i in range(len(gv.ps)):
            s = gv.ps[i]
            if s[0] is not 0 :
                if p.has_key(s[0]):
                    p[s[0]][i] = 1
                else:
                    p[s[0]] = [0] * len(gv.scontrol.stations)
                    p[s[0]][i] = 1

        for p, s in p.items():
            pgr = get_sip_status('Prg ' + str(p) + " - ", s)
            message_queue.put(pgr)


def notify_restart(name, **kw):
    message_queue.put("SYSTEM IS BEING RESTARTED!!!!!!")


zones = signal('zone_change')
zones.connect(notify_zone_change)
restart = signal('restart')
restart.connect(notify_restart)

################################################################################
# Helper functions:                                                            #
################################################################################


def get_sip_status(status = "", stations = []):
    if stations == []:
        s = gv.scontrol.stations
    else:
        s = stations
    first_on = None
    i = 0
    for i in range(len(s)):
        if s[i] == 1:
            # This station is On!
            if first_on is None:
                first_on = i
        else:
            if first_on is None:
                continue
            else:
                if first_on == (i -1):
                    status = status + str(i) + " "
                else:
                    status = status + str(first_on + 1 ) + "-" + str(i) + " "
                first_on = None

    if first_on is not None:
        if first_on == (i):
            status = status + str(i + 1) + " "
        else:
            status = status + str(first_on + 1 ) + "-" + str(i + 1) + " "

    if status == "":
        return "Idle"
    else:
        return status



################################################################################
# Web pages:                                                                   #
################################################################################


class settings(ProtectedPage):
    """Load an html page for entering lcd adjustments."""

    def GET(self):
        return template_render.lcd_button(get_lcd_options())


class settings_json(ProtectedPage):
    """Returns plugin settings in JSON format."""

    def GET(self):
        web.header('Access-Control-Allow-Origin', '*')
        web.header('Content-Type', 'application/json')
        return json.dumps(get_lcd_options())


class update(ProtectedPage):
    """Save user input to lcd_button.json file."""

    def GET(self):
        qdict = web.input()

        r = {}
        for opt in get_lcd_options():
            p = opt[0]
            datatype = opt[2]
            if datatype == 'int':
                value = qdict['o' + p]
                value = int(value)
            elif datatype == 'hex':
                value = qdict['o' + p]
                value = int(value,16)
            elif datatype == 'array':
                # can be a string or int array
                value = qdict['o' + p]
                l = []
                for v in [x.strip() for x in value.split(',')]:
                    if v.isdigit():
                        l.append(int(v))
                    else:
                        l.append(v)
                value = l
            elif datatype == 'boolean':
                if qdict.has_key('o' + p):
                    value = qdict['o' + p]
                    if value == 'on':
                        value = True
                    else:
                        value = False
                else:
                    value = False
            elif datatype == "textarea":
                continue
            else:
                value = qdict['o' + p]

            r[p] = value


        with open('./data/lcd_button.json', 'w') as f:  # write the settings to file
            json.dump(r, f)

        checker.update()
        raise web.seeother('/')
