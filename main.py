#!/usr/bin/env python3
# Three-stage warm-up + Early-End Calibration
# Stage 1: Aggressive warm-up (AIR allowed up to 34°C), exit when SAMPLE >= target
# Stage 2: Fans-only cool-down until AIR <= safe cutoff
# Stage 3: Normal hold (AIR-only band control)
# Emergency reverse is only for extremes. Calibration can end early when Sample reaches target band.

import os, time, json, csv, subprocess
from datetime import datetime
from threading import Timer
from statistics import mean
from collections import deque

from gpiozero import Button, PWMOutputDevice, DigitalOutputDevice
from RPLCD.i2c import CharLCD

# === Debugging Mode ===
# Toggle this to enable/disable verbose debug logging.
DEBUG = True  # Set to False to turn off debug logs

import logging

def _setup_logger():
    global logger
    logger = logging.getLogger("ferment")
    # Ensure log directory exists
    debug_dir = os.path.join(LOG_DIR, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    # File handler (daily file)
    file_path = os.path.join(debug_dir, datetime.now().strftime("debug_%Y-%m-%d.log"))
    fh = logging.FileHandler(file_path)
    # Console handler
    ch = logging.StreamHandler()
    # Formatter
    fmt = logging.Formatter("%(asctime)s [%(levelname)-7s] [%(name)-12s] %(message)s")
    fh.setFormatter(fmt); ch.setFormatter(fmt)
    # Avoid duplicate handlers if re-run
    logger.handlers.clear()
    logger.addHandler(fh); logger.addHandler(ch)
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    fh.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    ch.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    logger.debug("Debug logging initialized. DEBUG=%s", DEBUG)

# Placeholder in case logger is referenced before setup (minimal no-op logger)
class _NoopLogger:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def exception(self, *a, **k): pass

logger = _NoopLogger()

# --- Category loggers (for clearer labels) ---
log_sensor = logger.getChild("sensor")
log_buttons = logger.getChild("buttons")
log_mode   = logger.getChild("mode")
log_cal    = logger.getChild("cal")
log_motor  = logger.getChild("motor")
log_fan    = logger.getChild("fan")
log_emerg  = logger.getChild("emerg")
log_ui     = logger.getChild("ui")
log_io     = logger.getChild("io")
log_sys    = logger.getChild("sys")



FAN_SPEED = 0.75
LOOP_INTERVAL_SEC = 15
FAN_AFTER_OFF_SEC = 10
CAL_WINDOW_MIN = 200
CAL_EARLY_END_ENABLED = True          # End calibration early when Sample reaches target band
CAL_EARLY_END_STABLE_MIN = 0          # Minutes Sample must stay in-band before ending (0 = immediate)

CAL_TARGET_C = {'Sourdough': 27.0, 'Kombucha': 25.0, 'Water Kefir': 25.0}
RECOMMENDED_BAND_WIDTH = 1.0

STAGE_PARAMS = {
    'Sourdough':   {'startup_air_ceiling': 34.0, 'sample_exit_c': 27.0, 'cooldown_air_safe': 28.5},
    'Kombucha':    {'startup_air_ceiling': 34.0, 'sample_exit_c': 25.0, 'cooldown_air_safe': 27.0},
    'Water Kefir': {'startup_air_ceiling': 34.0, 'sample_exit_c': 25.0, 'cooldown_air_safe': 26.5},
}

EMERGENCY_INSTANT_AIR_C = 36.0
EMERGENCY_SUSTAIN_AIR_C = 34.5
EMERGENCY_SUSTAIN_SEC   = 60

BASE_DIR_APP = "/home/rpizero/Ferment"
LOG_DIR = os.path.join(BASE_DIR_APP, "logs")
CAL_FILE = os.path.join(BASE_DIR_APP, "calibration_setpoints.json")
os.makedirs(LOG_DIR, exist_ok=True)

_setup_logger()

lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2)

button_up=Button(17); button_down=Button(27); button_left=Button(23); button_right=Button(22); button_confirm=Button(26)
motor_pwm = PWMOutputDevice(20); motor_dir = DigitalOutputDevice(21)
fan1 = PWMOutputDevice(12); fan2 = PWMOutputDevice(13)
motor_pwm.value=0.0; fan1.value=0.0; fan2.value=0.0; motor_dir.value=False
log_sys.info("GPIO initialized: motor PWM=20 DIR=21, fans PWM=12/13, buttons 17/27/23/22/26, LCD 0x27")

os.system('modprobe w1-gpio'); os.system('modprobe w1-therm')
BASE_DIR='/sys/bus/w1/devices/'
SENSORS={'Sensor1':'28-7db6d445e7a7','Sensor2':'28-37e5d44570c3','Sample':'28-3ce1e3800798'}

MENU=['Sourdough','Kombucha','Water Kefir','Cal Sourdough','Cal Kombucha','Cal Water Kefir','Shutdown']
RANGES={'Sourdough':(27.8,28.8),'Kombucha':(25.5,26.5),'Water Kefir':(24.8,25.8)}

motor_on=False; reversing=False; fan_off_timer=None; request_pause_menu=False
_overtemp_start_ts=None

def load_calibration_setpoints():
    if not os.path.exists(CAL_FILE): return
    try:
        with open(CAL_FILE,'r') as f: data=json.load(f)
        changed=False
        for mode,vals in data.items():
            if isinstance(vals,dict) and 'low' in vals and 'high' in vals:
                low=float(vals['low']); high=float(vals['high'])
                if mode in RANGES and (low,high)!=RANGES[mode]: RANGES[mode]=(low,high); changed=True
        if changed:
            log_io.info('Loaded calibration_setpoints.json and applied to ranges'); show_two_line('Loaded saved','cal setpoints'); time.sleep(1.2)
    except Exception:
        log_io.warning('Calibration setpoints file load error; using defaults'); show_two_line('Cal file error','Using defaults'); time.sleep(1.5)

def save_calibration_setpoints(mode_name, low, high):
    data={}
    if os.path.exists(CAL_FILE):
        try:
            with open(CAL_FILE,'r') as f: data=json.load(f)
        except Exception: data={}
    data[mode_name]={'low':round(low,2),'high':round(high,2)}; log_io.info('Persisting cal setpoints for %s: low=%.2f high=%.2f', mode_name, low, high)
    tmp=CAL_FILE+'.tmp'
    with open(tmp,'w') as f: json.dump(data,f,indent=2)
    os.replace(tmp,CAL_FILE)

def get_log_file():
    return os.path.join(LOG_DIR, datetime.now().strftime('%Y-%m-%d') + '.csv')
def _write_header_if_needed(path):
    if not os.path.exists(path):
        with open(path,'w',newline='') as file:
            csv.writer(file).writerow(['Timestamp','Mode','Temp1_C','Temp2_C','Sample_C','Stage','Motor','Direction','Fans','Reversing'])
def init_log():
    log=get_log_file(); _write_header_if_needed(log)
    with open(log,'a',newline='') as f:
        csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'*** STARTUP ***','','','','','','','',''])
def log_data(mode,t1,t2,t_sample,stage,motor_on_state,dir_value,fans_on_state,rev_state):
    log=get_log_file(); _write_header_if_needed(log)
    with open(log,'a',newline='') as f:
        csv.writer(f).writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), mode or '',
            f'{t1:.2f}' if t1 is not None else 'ERR', f'{t2:.2f}' if t2 is not None else 'ERR',
            f'{t_sample:.2f}' if t_sample is not None else 'ERR', stage,
            'ON' if motor_on_state else 'OFF', 'A' if not dir_value else 'B',
            'ON' if fans_on_state else 'OFF', 'YES' if rev_state else 'NO'
        ])

def write_calibration_report(mode,target,air_avg,sample_avg,offset,rec_low,rec_high):
    ts=datetime.now().strftime('%Y-%m-%d_%H-%M-%S'); path=os.path.join(LOG_DIR,f'calibration_{mode}_{ts}.txt')
    with open(path,'w') as f:
        f.write(f'Calibration Report - {mode}\\n')
        f.write(f'Timestamp: {datetime.now().isoformat(timespec="seconds")}\\n\\n')
        f.write(f'Target SAMPLE temperature: {target:.2f} °C\\n')
        f.write(f'Window length: {CAL_WINDOW_MIN} minutes\\n\\n')
        f.write(f'Average AIR (mean of Sensor1 & Sensor2): {air_avg:.2f} °C\\n')
        f.write(f'Average SAMPLE: {sample_avg:.2f} °C\\n')
        f.write(f'Computed offset (AIR - SAMPLE): {offset:.2f} °C\\n\\n')
        f.write('Recommended AIR setpoints:\\n')
        f.write(f'  Low:  {rec_low:.2f} °C\\n')
        f.write(f'  High: {rec_high:.2f} °C\\n')
        f.write('\\nPersisted to: calibration_setpoints.json\\n')
    return path

def read_temp(sensor_id):
    path=os.path.join(BASE_DIR, sensor_id, 'w1_slave')
    try:
        with open(path) as f: lines=f.readlines()
        if not lines or lines[0].strip().endswith('NO'):
            log_sensor.warning('CRC/NO for %s', sensor_id); return None
        t_pos=lines[1].find('t=')
        if t_pos==-1:
            log_sensor.warning('read_temp parse error for %s: no t=', sensor_id); return None
        val = round(float(lines[1][t_pos+2:])/1000.0,2); log_sensor.debug('%s = %.2f C', sensor_id, val); return val
    except Exception as e:
        log_sensor.error('read_temp exception for %s: %s', sensor_id, e); return None

def fans_on():
    fan1.value=FAN_SPEED; fan2.value=FAN_SPEED; log_fan.debug('Fans ON at duty=%.2f', FAN_SPEED)
def fans_off():
    fan1.value=0.0; fan2.value=0.0; log_fan.debug('Fans OFF')
def cancel_fan_timer():
    global fan_off_timer
    if fan_off_timer: fan_off_timer.cancel(); fan_off_timer=None
def schedule_fan_off(delay=FAN_AFTER_OFF_SEC):
    log_fan.debug('Scheduling fans OFF in %ds', delay)
    global fan_off_timer
    cancel_fan_timer(); fan_off_timer=Timer(delay,fans_off); fan_off_timer.start()

def show_two_line(a,b):
    lcd.clear(); lcd.write_string(a[:16]); lcd.cursor_pos=(1,0); lcd.write_string(b[:16])
def show_menu(options,index):
    show_two_line(f'> {options[index][:14]}', f'  {options[(index+1)%len(options)][:14]}')
def status_display(mode,t_air,stage,high):
    stage_map={'startup':'HOT','cooldown':'VENT','hold':'HOLD','rev':'REV!'}
    tag=stage_map.get(stage,''); line1=f'{mode[:10]} {tag}'.strip()[:16]; t_air=0.0 if t_air is None else t_air
    show_two_line(line1, f'{t_air:.1f}C/{high:.0f}C')

def wait_for_button_any():
    while True:
        if button_up.is_pressed: log_buttons.debug('UP pressed'); time.sleep(0.2); return 'UP'
        if button_down.is_pressed: log_buttons.debug('DOWN pressed'); time.sleep(0.2); return 'DOWN'
        if button_left.is_pressed: log_buttons.debug('LEFT pressed'); time.sleep(0.2); return 'LEFT'
        if button_right.is_pressed: log_buttons.debug('RIGHT pressed'); time.sleep(0.2); return 'RIGHT'
        if button_confirm.is_pressed: log_buttons.debug('CONFIRM pressed'); time.sleep(0.2); return 'CONFIRM'
        time.sleep(0.05)

def select_from_menu(options,initial_index=0,cancel_with_left=False):
    idx=initial_index; show_menu(options,idx)
    while True:
        btn=wait_for_button_any()
        if btn=='UP': idx=(idx-1)%len(options); show_menu(options,idx)
        elif btn=='DOWN': idx=(idx+1)%len(options); show_menu(options,idx)
        elif btn=='CONFIRM': return idx
        elif cancel_with_left and btn=='LEFT': return None

def on_left_pressed():
    log_buttons.debug('LEFT pressed => pause menu request')
    global request_pause_menu; request_pause_menu=True
button_left.when_pressed=on_left_pressed

def safe_stop():
    log_sys.info('Safe stop: motor OFF, fans OFF')
    global motor_on
    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_off()
def shutdown_now():
    log_sys.info('Shutdown requested via menu/button')
    log=get_log_file(); _write_header_if_needed(log)
    with open(log,'a',newline='') as f: csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'*** SHUTDOWN ***','','','','','','','',''])
    safe_stop(); log_ui.info('LCD: Shutting down'); show_two_line('Shutting down',''); time.sleep(1); subprocess.call(['sudo','shutdown','now'])
def pause_menu():
    log_buttons.debug('Entering pause menu')
    sel=select_from_menu(['Resume','Change Mode','Shutdown'],0,True)
    choice = 'resume' if sel in (None,0) else ('change' if sel==1 else 'shutdown'); log_buttons.info('Pause choice: %s', choice); return choice

def _read_air_and_sample():
    t1=read_temp(SENSORS['Sensor1']); t2=read_temp(SENSORS['Sensor2']); t_sample=read_temp(SENSORS['Sample'])
    air_vals=[t for t in (t1,t2) if t is not None]; air=None if not air_vals else mean(air_vals); tmax=None if not air_vals else max(air_vals)
    return t1,t2,t_sample,air,tmax

def _emergency_reverse_guard(air,high):
    global reversing, motor_on, _overtemp_start_ts
    if air is None: return
    now=time.time()
    if air>=EMERGENCY_INSTANT_AIR_C and not reversing:
        log_emerg.warning('Emergency reverse (instant): air=%.2f ≥ %.2f', air, EMERGENCY_INSTANT_AIR_C)
        reversing=True; motor_dir.value=not motor_dir.value; motor_pwm.value=1.0; cancel_fan_timer(); fans_on(); _overtemp_start_ts=None; return
    if air>=EMERGENCY_SUSTAIN_AIR_C:
        if _overtemp_start_ts is None: _overtemp_start_ts=now
        elif (now-_overtemp_start_ts)>=EMERGENCY_SUSTAIN_SEC and not reversing:
            log_emerg.warning('Emergency reverse (sustain): air=%.2f for ≥%ds', air, EMERGENCY_SUSTAIN_SEC)
            reversing=True; motor_dir.value=not motor_dir.value; motor_pwm.value=1.0; cancel_fan_timer(); fans_on(); _overtemp_start_ts=None
    else:
        _overtemp_start_ts=None
    if reversing and air<=(high-1.0):
        log_emerg.info('Emergency reverse end: air=%.2f ≤ %.2f', air, (high-1.0))
        reversing=False; motor_pwm.value=0.0; schedule_fan_off(); motor_on=False; motor_dir.value=False

def run_mode(mode_name,low,high):
    global motor_on,reversing,request_pause_menu
    motor_dir.value=False; motor_on=False; reversing=False; cancel_fan_timer(); fans_off()
    stage='startup'; params=STAGE_PARAMS.get(mode_name,STAGE_PARAMS['Sourdough'])
    startup_ceiling=params['startup_air_ceiling']; sample_exit_c=params['sample_exit_c']; cooldown_safe=params['cooldown_air_safe']
    while True:
        t1,t2,t_sample,air,tmax=_read_air_and_sample(); status_display(mode_name,air,stage,high)
        fans_on_state=(fan1.value>0) or (fan2.value>0); log_data(mode_name,t1,t2,t_sample,stage,motor_on,motor_dir.value,fans_on_state,reversing)
        _emergency_reverse_guard(air,high)
        if not reversing:
            if stage=='startup':
                if (t_sample is not None) and (t_sample>=sample_exit_c):
                    log_mode.info('%s: startup → cooldown (Sample %.2f ≥ %.2f)', mode_name, t_sample, sample_exit_c)
                    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); stage='cooldown'
                else:
                    if (air is not None) and (air>=startup_ceiling):
                        log_mode.debug('Startup ceiling: air=%.2f ≥ %.2f → motor OFF, fans ON', air, startup_ceiling)
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                    else:
                        log_mode.debug('Startup heating: motor ON (A), fans ON');
                        motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
            elif stage=='cooldown':
                motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                if (air is not None) and (air<=cooldown_safe): logger.info('Stage transition: cooldown -> hold (air %.2f <= %.2f)', air, cooldown_safe); schedule_fan_off(); stage='hold'
            else:
                if tmax is not None:
                    if motor_on and tmax>high:
                        log_mode.debug('Hold: tmax %.2f > high %.2f → motor OFF, purge', tmax, high)
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); schedule_fan_off()
                    if (not motor_on) and tmax<=low:
                        log_mode.debug('Hold: tmax %.2f ≤ low %.2f → motor ON', tmax, low)
                        motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
        for _ in range(int(LOOP_INTERVAL_SEC/0.1)):
            if request_pause_menu:
                choice=pause_menu()
                if choice=='resume': request_pause_menu=False; break
                elif choice=='change': request_pause_menu=False; safe_stop(); return 'change'
                elif choice=='shutdown': shutdown_now(); return 'shutdown'
            time.sleep(0.1)

def run_calibration(mode_name,low,high):
    global motor_on,reversing,request_pause_menu
    finish_requested=False
    def _on_confirm():
        nonlocal finish_requested; finish_requested=True
    old=button_confirm.when_pressed; button_confirm.when_pressed=_on_confirm
    try:
        target=CAL_TARGET_C.get(mode_name,25.0); motor_dir.value=False; motor_on=False; reversing=False; cancel_fan_timer(); fans_off()
        maxlen=max(1,int((CAL_WINDOW_MIN*60)/LOOP_INTERVAL_SEC)); air_buf=deque(maxlen=maxlen); sample_buf=deque(maxlen=maxlen)
        params=STAGE_PARAMS.get(mode_name,STAGE_PARAMS['Sourdough'])
        startup_ceiling=params['startup_air_ceiling']; sample_exit_c=params['sample_exit_c']; cooldown_safe=params['cooldown_air_safe']
        stage='startup'; start_ts=time.time()
        # Early-end trackers
        stable_secs=0.0; last_ts=time.time()
        show_two_line(f'Cal {mode_name}'[:16],'Confirm=Finish')
        while True:
            t1,t2,t_sample,air,tmax=_read_air_and_sample()
            tag={'startup':'HOT','cooldown':'VENT','hold':'HOLD','rev':'REV'}.get(stage,'')
            if (air is not None) and (t_sample is not None): show_two_line(f'Cal {mode_name} {tag}'[:16], f'A:{air:.1f} S:{t_sample:.1f}')
            else: show_two_line(f'Cal {mode_name}'[:16],'Waiting temps')
            fans_on_state=(fan1.value>0) or (fan2.value>0); log_data(f'CAL-{mode_name}',t1,t2,t_sample,stage,motor_on,motor_dir.value,fans_on_state,reversing)
            _emergency_reverse_guard(air,high)
            if not reversing:
                if stage=='startup':
                    if (t_sample is not None) and (t_sample>=sample_exit_c):
                        log_mode.info('%s: startup → cooldown (Sample %.2f ≥ %.2f)', mode_name, t_sample, sample_exit_c)
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); stage='cooldown'
                    else:
                        if (air is not None) and (air>=startup_ceiling):
                            log_mode.debug('Startup ceiling: air=%.2f ≥ %.2f → motor OFF, fans ON', air, startup_ceiling)
                            motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                        else:
                            motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
                elif stage=='cooldown':
                    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                    if (air is not None) and (air<=cooldown_safe): logger.info('Stage transition: cooldown -> hold (air %.2f <= %.2f)', air, cooldown_safe); schedule_fan_off(); stage='hold'
                else:
                    if tmax is not None:
                        if motor_on and tmax>high:
                            log_mode.debug('Hold: tmax %.2f > high %.2f → motor OFF, purge', tmax, high)
                            motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); schedule_fan_off()
                        if (not motor_on) and tmax<=low:
                            log_mode.debug('Hold: tmax %.2f ≤ low %.2f → motor ON', tmax, low)
                            motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
            # Buffers
            if air is not None: air_buf.append(air)
            if t_sample is not None: sample_buf.append(t_sample)
            # Early end: Sample in target band for configured stability
            target_low = target - 0.5; target_high = target + 0.5
            now_ts=time.time(); dt=now_ts-last_ts; last_ts=now_ts
            in_band = (t_sample is not None) and (t_sample>=target_low) and (t_sample<=target_high)
            stable_secs = stable_secs + dt if in_band else 0.0
            # Finish conditions
            elapsed=time.time()-start_ts
            required_stable = max(0, CAL_EARLY_END_STABLE_MIN) * 60
            if finish_requested or elapsed >= CAL_WINDOW_MIN*60 or (CAL_EARLY_END_ENABLED and stable_secs >= required_stable and in_band):
                log_cal.info('Finish: requested=%s, elapsed=%.0fs, early_end=%s (stable=%.0fs≥%ds, in_band=%s)', finish_requested, elapsed, CAL_EARLY_END_ENABLED and stable_secs >= required_stable and in_band, stable_secs, required_stable, in_band)
                break
            # Pause & pacing
            for _ in range(int(LOOP_INTERVAL_SEC/0.1)):
                if finish_requested: break
                if request_pause_menu:
                    choice=pause_menu()
                    if choice=='resume': request_pause_menu=False; break
                    elif choice=='change': request_pause_menu=False; safe_stop(); return 'change'
                    elif choice=='shutdown': shutdown_now(); return 'shutdown'
                time.sleep(0.1)
            if finish_requested: break
        if len(air_buf)==0 or len(sample_buf)==0:
            show_two_line('Cal failed','No data'); time.sleep(2); return 'change'
        air_avg=mean(air_buf); sample_avg=mean(sample_buf); offset=air_avg-sample_avg
        center=target+offset; half=RECOMMENDED_BAND_WIDTH/2.0; rec_low,rec_high=center-half,center+half
        save_calibration_setpoints(mode_name,rec_low,rec_high); RANGES[mode_name]=(rec_low,rec_high); log_cal.info('Applied setpoints for %s: L=%.2f H=%.2f', mode_name, rec_low, rec_high)
        write_calibration_report(mode_name,target,air_avg,sample_avg,offset,rec_low,rec_high); log_io.debug('Wrote calibration report file')
        show_two_line('Cal saved+applied', f'L:{rec_low:.1f} H:{rec_high:.1f}'); time.sleep(4); return 'change'
    finally:
        button_confirm.when_pressed=old

def main_menu():
    idx=0; show_menu(MENU,idx)
    while True:
        btn=wait_for_button_any()
        if btn=='UP': idx=(idx-1)%len(MENU); show_menu(MENU,idx)
        elif btn=='DOWN': idx=(idx+1)%len(MENU); show_menu(MENU,idx)
        elif btn=='CONFIRM':
            choice=MENU[idx]
            if choice=='Shutdown': shutdown_now(); return ('shutdown',)
            elif choice.startswith('Cal '):
                base=choice.replace('Cal ',''); low,high=RANGES[base]; log_mode.debug('Menu: select calibration %s (L=%.2f H=%.2f)', base, low, high); return ('cal',base,low,high)
            else:
                low,high=RANGES[choice]; log_mode.debug('Menu: select mode %s (L=%.2f H=%.2f)', choice, low, high); return ('mode',choice,low,high)

def main():
    log_sys.info('Fermentation Controller starting...')
    load_calibration_setpoints(); init_log(); log_sys.info('Main menu ready')
    while True:
        sel=main_menu()
        if sel[0]=='shutdown': return
        if sel[0]=='mode':
            log_mode.info('Start mode: %s (Low=%.2f High=%.2f)', sel[1], sel[2], sel[3])
            _,mode_name,low,high=sel; result=run_mode(mode_name,low,high)
            if result=='shutdown': return
        elif sel[0]=='cal':
            log_cal.info('Start calibration: %s (Low=%.2f High=%.2f)', sel[1], sel[2], sel[3])
            _,mode_name,low,high=sel; result=run_calibration(mode_name,low,high)
            if result=='shutdown': return

if __name__=='__main__': main()