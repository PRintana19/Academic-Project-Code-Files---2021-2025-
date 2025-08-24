import machine
import utime
import dht
from i2c_lcd import I2cLcd  # Make sure your MicroPython i2c_lcd.py and lcd_api.py are on the Pico

# ======= Hardware Setup =======

# DHT11 sensor on GPIO14
dht_sensor = dht.DHT11(machine.Pin(14))

# Motor driver outputs (assume HIGH = motor ON)
motor1 = machine.Pin(10, machine.Pin.OUT)
motor2 = machine.Pin(11, machine.Pin.OUT)
motor1.value(0)
motor2.value(0)

# Buttons (active low, using internal pull-ups)
# Adjust these pins as needed.
btn_up    = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
btn_down  = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)
btn_menu  = machine.Pin(6, machine.Pin.IN, machine.Pin.PULL_UP)
btn_back  = machine.Pin(7, machine.Pin.IN, machine.Pin.PULL_UP)

# I2C LCD display on I2C bus 0 with SDA on GPIO8, SCL on GPIO9
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8), freq=400000)
# Print the I2C scan result to verify (expected address is often 0x27 or 0x3F)
print("I2C scan:", i2c.scan())
lcd = I2cLcd(i2c, 0x27, 2, 16)  # Change 0x27 if needed

# RTC for current date and time (Pico has a software RTC)
rtc = machine.RTC()
# Optionally, set the RTC if it isn’t already set. Format:
# rtc.datetime((year, month, day, weekday, hour, minute, second, subseconds))
# Example:
# rtc.datetime((2023, 2, 8, 2, 12, 0, 0, 0))

# ======= Global Variables =======

set_temp = 25  # Default set temperature (in Celsius), allowed range 0-35
menu_state = 0  # 0: Main screen; 1: Show current time; 2: Show current date; 3: Adjust set temp; 4: Save confirmation
motor2_off_timer = None  # For delaying motor2 off (in milliseconds)

# ======= Helper Functions =======

def wait_for_release(btn):
    """Simple debounce: wait until the button is released."""
    while btn.value() == 0:
        utime.sleep_ms(10)
    utime.sleep_ms(200)  # additional debounce delay

def update_display(current_temp, set_temp, menu_state):
    """Update the LCD display based on the current menu state."""
    lcd.clear()
    if menu_state == 0:
        # Main screen: show current measured temp and set temp.
        if current_temp is None:
            lcd.putstr("Temp: -- C")
        else:
            lcd.putstr("Temp: {} C".format(current_temp))
        lcd.move_to(0, 1)
        lcd.putstr("Set: {} C".format(set_temp))
    elif menu_state == 1:
        # Show current time.
        dt = rtc.datetime()  # (year, month, day, weekday, hour, minute, second, subseconds)
        lcd.putstr("Time: {:02d}:{:02d}:{:02d}".format(dt[4], dt[5], dt[6]))
    elif menu_state == 2:
        # Show current date.
        dt = rtc.datetime()
        lcd.putstr("Date: {:04d}-{:02d}-{:02d}".format(dt[0], dt[1], dt[2]))
    elif menu_state == 3:
        # Adjust set temperature.
        lcd.putstr("Adjust Set Temp:")
        lcd.move_to(0, 1)
        lcd.putstr("Set: {} C".format(set_temp))
    elif menu_state == 4:
        # Save confirmation.
        lcd.putstr("Save set temp?")
        lcd.move_to(0, 1)
        lcd.putstr("Press Menu to OK")

# ======= Main Loop =======

while True:
    # Read temperature from the DHT11 sensor.
    try:
        dht_sensor.measure()
        current_temp = dht_sensor.temperature()
    except Exception as e:
        current_temp = None

    # --- Menu Handling ---
    # Use btn_menu to cycle through menu states.
    if btn_menu.value() == 0:
        menu_state = (menu_state + 1) % 5
        wait_for_release(btn_menu)
    
    # In the "Adjust set temp" menu (state 3), use btn_up and btn_down.
    if menu_state == 3:
        if btn_up.value() == 0:
            if set_temp < 35:
                set_temp += 1
            wait_for_release(btn_up)
        if btn_down.value() == 0:
            if set_temp > 0:
                set_temp -= 1
            wait_for_release(btn_down)
    
    # In the "Save confirmation" menu (state 4), pressing btn_menu saves the new set_temp.
    if menu_state == 4:
        if btn_menu.value() == 0:
            # Save confirmed; return to main screen.
            menu_state = 0
            wait_for_release(btn_menu)
    
    # Update LCD display based on menu state.
    update_display(current_temp, set_temp, menu_state)
    
    # --- Motor Control Logic ---
    # Compare current measured temperature to the user-set temperature.
    if current_temp is not None:
        if set_temp < current_temp:
            # If set temperature is lower than current temperature:
            # Turn ON both motors.
            motor1.value(1)
            motor2.value(1)
            motor2_off_timer = None  # Reset the timer if it was running.
        else:
            # If set temperature is greater than or equal to current temperature:
            # Turn OFF motor1 immediately.
            motor1.value(0)
            # Start a timer to turn OFF motor2 after 2 minutes (120,000 ms).
            if motor2_off_timer is None:
                motor2_off_timer = utime.ticks_ms()
            if utime.ticks_diff(utime.ticks_ms(), motor2_off_timer) >= 120000:
                motor2.value(0)
            else:
                # Until 2 minutes have passed, keep motor2 ON.
                motor2.value(1)
    else:
        # If the sensor reading fails, turn off both motors for safety.
        motor1.value(0)
        motor2.value(0)
    
    utime.sleep_ms(200)
