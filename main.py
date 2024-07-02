import time
import sqlite3
import serial
import datetime
import RPi.GPIO as GPIO
import adafruit_fingerprint
from signal import signal, SIGTERM, SIGHUP, pause
from rpi_lcd import LCD

# GPIO setup
RED_LED_PIN = 17
YELLOW_LED_PIN = 27
GREEN_LED_PIN = 22
RELAY_PIN = 26

# Ensure any previous settings are cleaned up
GPIO.setwarnings(False)
GPIO.cleanup()

GPIO.setmode(GPIO.BCM)
GPIO.setup(RED_LED_PIN, GPIO.OUT)
GPIO.setup(YELLOW_LED_PIN, GPIO.OUT)
GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
GPIO.setup(RELAY_PIN, GPIO.OUT)

# Ensure the relay is initially turned off
GPIO.output(RELAY_PIN, GPIO.HIGH)

# Initialize LCD
lcd = LCD()

# Initialize fingerprint sensor
uart = serial.Serial("/dev/ttyUSB0", baudrate=57600, timeout=1)
finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)

# Database connections
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

conn_user = sqlite3.connect('userdb.db')
conn_user.row_factory = dict_factory
cursor_user = conn_user.cursor()

conn_log = sqlite3.connect('logdb.db')
cursor_log = conn_log.cursor()

# Create log table
cursor_log.execute('''
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    timestamp TEXT NOT NULL
)
''')

def safe_exit(signum, frame):
    lcd.clear()
    GPIO.cleanup()
    conn_user.close()
    conn_log.close()
    exit(1)

signal(SIGTERM, safe_exit)
signal(SIGHUP, safe_exit)

# def check_expiry_dates(row):
    # current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    # return all([
        # row['license_expiry_date'] >= current_date,
        # row['puc_expiry_date'] >= current_date,
        # row['insurance_expiry_date'] >= current_date,
        # row['rc_validity_date'] >= current_date
    # ])
    
def check_expiry_dates(row):
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    lcd.text(f"Checking license: {row['license_expiry_date']}", 1)
    print(f"Checking license: {row['license_expiry_date']}")
    lcd.clear()
    lcd.text(f"Checking license: {row['license_expiry_date']}", 3)
    time.sleep(2)
    if row['license_expiry_date'] < current_date:
        return False
    
    lcd.text(f"Checking PUC: {row['puc_expiry_date']}", 1)
    print(f"Checking PUC: {row['puc_expiry_date']}")
    lcd.clear()
    lcd.text(f"Checking PUC: {row['puc_expiry_date']}", 3)
    time.sleep(2)
    if row['puc_expiry_date'] < current_date:
        return False
    
    lcd.text(f"Checking insurance: {row['insurance_expiry_date']}", 1)
    print(f"Checking insurance: {row['insurance_expiry_date']}")
    lcd.clear()
    lcd.text(f"Checking insurance: {row['insurance_expiry_date']}", 3)
    time.sleep(2)
    if row['insurance_expiry_date'] < current_date:
        return False
    
    lcd.text(f"Checking RC: {row['rc_validity_date']}", 1)
    print(f"Checking RC: {row['rc_validity_date']}")
    lcd.clear()
    lcd.text(f"Checking RC: {row['rc_validity_date']}", 3)
    time.sleep(2)
    lcd.clear()
    if row['rc_validity_date'] < current_date:
        return False
    
    return True

def verify_fingerprint():
    print("Waiting for image...")
    lcd.text("Waiting for image...", 1)
    while finger.get_image() != adafruit_fingerprint.OK:
        pass
    print("Templating...")
    lcd.text("Templating...", 1)
    if finger.image_2_tz(1) != adafruit_fingerprint.OK:
        print("Failed to template")
        lcd.text("Templating failed", 1)
        return False
    print("Searching...")
    lcd.text("Searching...", 1)
    if finger.finger_search() != adafruit_fingerprint.OK:
        print("Failed to find fingerprint")
        lcd.text("No match found", 1)
        return False
    print(f"Found fingerprint with ID: {finger.finger_id}")
    return True

def process_verification():
    GPIO.output(YELLOW_LED_PIN, GPIO.HIGH)
    lcd.clear()
    lcd.text("Welcome", 1)
    time.sleep(2)
    lcd.clear()
    lcd.text("Vehicle Boot", 1)
    time.sleep(3)
    lcd.clear()
    lcd.text("Processing...", 1)
    time.sleep(2)
    lcd.clear()
    lcd.text("Please Scan", 1)
    lcd.text("Fingerprint", 2)
    lcd.text(" - - - - ", 3)
    time.sleep(3)

    if verify_fingerprint():
        
        user_id = finger.finger_id
        cursor_user.execute("SELECT * FROM users WHERE fingerprint_id=?", (user_id,))
        row = cursor_user.fetchone()
        if row:
            lcd.text(f"Welcome {row['name']}", 1)
            print(f"Welcome {row['name']}")
            time.sleep(2)
            if check_expiry_dates(row):
                lcd.text("Documents Valid", 1)
                print("Documents Valid")
                GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
                GPIO.output(RELAY_PIN, GPIO.LOW)
                lcd.text("Engine Started", 10)
                cursor_log.execute("INSERT INTO log (name, timestamp) VALUES (?, ?)", 
                                   (row['name'], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn_log.commit()
                time.sleep(10)
                GPIO.output(RELAY_PIN, GPIO.HIGH)
                GPIO.output(GREEN_LED_PIN, GPIO.LOW)
            else:
                GPIO.output(RED_LED_PIN, GPIO.HIGH)
                lcd.text("Invalid Documents", 2)
                print("Invalid Documents")
                time.sleep(5)
                GPIO.output(RED_LED_PIN, GPIO.LOW)
        else:
            GPIO.output(RED_LED_PIN, GPIO.HIGH)
            lcd.text("User Not Found", 2)
            print("User Not Found")
            time.sleep(5)
            GPIO.output(RED_LED_PIN, GPIO.LOW)
    else:
        GPIO.output(RED_LED_PIN, GPIO.HIGH)
        lcd.text("Fingerprint Error", 2)
        print("Fingerprint Error")
        time.sleep(5)
        GPIO.output(RED_LED_PIN, GPIO.LOW)

    GPIO.output(YELLOW_LED_PIN, GPIO.LOW)

try:
    lcd.clear()
    lcd.text("Scan Finger", 1)
    process_verification()
    time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    safe_exit(None, None)
