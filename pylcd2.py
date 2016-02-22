'''
'''

import smbus
import time

# General i2c device class so that other devices can be added easily
class i2c_device:
    def __init__(self, addr, port):
        self.addr = addr
        self.bus = smbus.SMBus(port)

    def write(self, byte):
        self.bus.write_byte(self.addr, byte)

    def read(self):
        return self.bus.read_byte(self.addr)

    def read_nbytes_data(self, data, n): # For sequential reads > 1 byte
        return self.bus.read_i2c_block_data(self.addr, data, n)


class lcd:
    #initializes objects and lcd
    '''
    For the LCD described here:
        http://www.raspberrypi-spy.co.uk/2015/05/using-an-i2c-enabled-lcd-screen-with-the-raspberry-pi/
    and available here:
        http://www.dx.com/es/p/i2c-iic-lcd-1602-display-module-with-white-backlight-4-pin-cable-for-arduino-raspberry-pi-374741
    '''
    # Some Constants
    LCD_WIDTH = 16
    LCD_CHR = 1 # Mode - Sending data
    LCD_CMD = 0 # Mode - Sending command

    LCD_LINE_ADDR = [0x80, 0xC0, 0x94, 0xD4] # LCD RAM address for each line

    LCD_BACKLIGHT  = 0x08  # On
    #LCD_BACKLIGHT = 0x00  # Off
    ENABLE = 0b00000100 # Enable bit

    # Timing constants
    E_PULSE = 0.0005
    E_DELAY = 0.0005

    def __init__(self, addr, port):
        self._bus = i2c_device(addr, port)
        self.i2c_address = addr

        # Initialise display
        self._lcd_byte(0x33,self.LCD_CMD) # 110011 Initialise
        self._lcd_byte(0x32,self.LCD_CMD) # 110010 Initialise
        self._lcd_byte(0x06,self.LCD_CMD) # 000110 Cursor move direction
        self._lcd_byte(0x0C,self.LCD_CMD) # 001100 Display On,Cursor Off, Blink Off
        self._lcd_byte(0x28,self.LCD_CMD) # 101000 Data length, number of lines, font size
        self._lcd_byte(0x01,self.LCD_CMD) # 000001 Clear display
        time.sleep(self.E_DELAY)

    def _lcd_byte(self, bits, mode):
        # Send byte to data pins
        # bits = the data
        # mode = 1 for data
        #        0 for command

        bits_high = mode | (bits & 0xF0) | self.LCD_BACKLIGHT
        bits_low = mode | ((bits<<4) & 0xF0) | self.LCD_BACKLIGHT

        # High bits
        self._bus.write(bits_high)
        self._lcd_toggle_enable(bits_high)

        # Low bits
        self._bus.write(bits_low)
        self._lcd_toggle_enable(bits_low)

    def _lcd_toggle_enable(self, bits):
          # Toggle enable
        time.sleep(self.E_DELAY)
        self._bus.write((bits | self.ENABLE))
        time.sleep(self.E_PULSE)
        self._bus.write((bits & ~self.ENABLE))
        time.sleep(self.E_DELAY)

    def lcd_string(self, message,line):
      # Send string to display
        line = self.LCD_LINE_ADDR[(line - 1)]

        message = message.ljust(self.LCD_WIDTH," ")

        self._lcd_byte(line, self.LCD_CMD)

        for i in range(self.LCD_WIDTH):
            self._lcd_byte(ord(message[i]),self.LCD_CHR)


    # put string function
    def lcd_puts(self, string, line):
        if len(string) > self.LCD_WIDTH:
            while len(string) > 10:
                self.lcd_string(string[:self.LCD_WIDTH], line)
                string = string[1:]
                time.sleep(0.3)
        else:
            self.lcd_string(string, line)

    # clear lcd and set to home
    def lcd_clear(self):
        self._lcd_byte(0x01,self.LCD_CMD) # 000001 Clear display
        #self._lcd_byte(0x02,self.LCD_CMD) # 000001 Clear display
        time.sleep(self.E_DELAY)

    def clear(self):
        self.lcd_clear()
