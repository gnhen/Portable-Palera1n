#!/usr/bin/env python3
import subprocess, time, signal, re, sys, RPi.GPIO as G
from RPLCD.i2c import CharLCD

R, GN, B = 17, 18, 15

G.setmode(G.BCM)
G.setup([R, GN], G.OUT, initial=[1, 0])
G.output(GN, 0)
G.setup(B, G.IN, pull_up_down=G.PUD_UP)

lcd = CharLCD('PCF8574', 0x27, cols=16, rows=2)
lcd.clear()
lcd.write_string('Payload Ready')

CMD = ['sudo', '/home/palera1n', '-f', '--cli']
ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

status_map = {
    'Waiting for devices': 'Waiting for Device',
    'Booting PongoOS': 'Booting PongoOS',
    'Entering DFU': 'Setting Up Device',
    'Exploit sent': 'Exploit sent!',
    'PongoOS booted': 'PongoOS Booted',
    'Booting Kernel': 'Booting Kernel',
    'Hold volume down + side button': 'Hold volume down + side button',
    'Hold volume down button': 'Hold volume down button',
}

def wait_for_button(prompt):
    lcd.clear(),
    lcd.write_string(prompt)
    while G.input(B):
        time.sleep(0.05)
    wait_for_debounced_release()

def wait_for_debounced_release():
    time.sleep(0.05)
    while not G.input(B):
        time.sleep(0.05)

def display_line(line):
    clean_line = ansi_escape.sub('', line.strip())
    print(clean_line)

    display_text = None

    if '<Info>:' in clean_line:
        info_text = clean_line.split('<Info>:')[1].strip()
        for key, msg in status_map.items():
            if key in info_text:
                info_text = msg
                break
        display_text = info_text

    else:
        for key, msg in status_map.items():
            if key in clean_line:
                display_text = msg
                break

    if display_text:
        display_text = (display_text + ' ' * 32)[:32]
        lcd.home()
        lcd.write_string(display_text[:16])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(display_text[16:32])

def run_once():
    G.output(GN, 1) 
    p = subprocess.Popen(CMD, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, stdin=subprocess.PIPE)
    saw_prompt = False
    global canceled_during_run
    try:
        for line in p.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            display_line(line)

            if 'press enter' in line.lower() and not saw_prompt:
                wait_for_button('Press button now')
                p.stdin.write('\n')
                p.stdin.flush()
                saw_prompt = True

            elif 'Booting Kernel...' in clean_line.lower():
                lcd.clear()
                lcd.write_string('Booting Kernel')
                p.send_signal(signal.SIGINT)
                p.wait()
                cleanup_and_exit()

            elif 'Booting PongoOS' in line:
                time.sleep(10)
                p.send_signal(signal.SIGINT)
                p.wait()
                return True

        p.wait()
        return False
    except:
        p.kill()
        return False
    finally:
        G.output(GN, 0) 

def launch():
    lcd.clear()
    lcd.write_string('Run 1')
    global canceled_during_run
    canceled_during_run = False

    if run_once():
        time.sleep(1)
        lcd.clear()
        lcd.write_string('Run 2')
        p = subprocess.Popen(CMD, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
        G.output(GN, 1) 
        for line in p.stdout:
            clean_line = ansi_escape.sub('', line.strip())
            display_line(line)

            if 'booting kernel' in clean_line.lower():
                lcd.clear()
                lcd.write_string('Booting Kernel')
                p.send_signal(signal.SIGINT)
                p.wait()
                cleanup_and_exit()
                exit()

        else:
            lcd.clear()
            lcd.write_string('Done' if p.returncode == 0 else 'Error')

        G.output(GN, 0) 
    else:
        if not canceled_during_run:
            lcd.clear()
            lcd.write_string('Error')

    lcd.home()
    lcd.write_string('Payload Ready')

def cleanup_and_exit():
    G.output(R, 0)
    G.output(GN, 0)
    lcd.clear()
    sys.exit(0)

try:
    while True:
        if not G.input(B):
            launch()
            wait_for_debounced_release()
        time.sleep(0.05)
finally:
    G.output(R, 0)
    G.output(GN, 0)
    lcd.clear()
