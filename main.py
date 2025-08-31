#!/usr/bin/env python3
# Fermentation Chamber Controller (Raspberry Pi Zero)
# Robust calibration + autostart + long-press pause in calibration

import os, time, json, csv, subprocess
from datetime import datetime
from threading import Timer
from statistics import mean
from collections import deque
from pathlib import Path

from gpiozero import Button, PWMOutputDevice, DigitalOutputDevice
from RPLCD.i2c import CharLCD

# ---------- Tunables ----------
FAN_SPEED = 0.75
LOOP_INTERVAL_SEC = 15
FAN_AFTER_OFF_SEC = 10

# Calibration timing / stability
CAL_WINDOW_MIN = 200
CAL_EARLY_END_ENABLED = True
CAL_EARLY_END_STABLE_MIN = 10
CAL_STABLE_WINDOW_MIN = 30
CAL_MIN_STABLE_MIN = 10
CAL_PAUSE_LONGPRESS_SEC = 1.0  # require long-press to open pause during calibration

# Offset & setpoint safety guards
OFFSET_MIN = -2.0
OFFSET_MAX = +5.0
RECOMMENDED_BAND_WIDTH = 1.0
RECO_MAX_HIGH = {'Sourdough': 33.0, 'Kombucha': 31.0, 'Water Kefir': 30.5}
RECO_MIN_LOW  = {'Sourdough': 26.0, 'Kombucha': 23.0, 'Water Kefir': 22.5}

# Boost stall protection
BOOST_MIN_RISE_C_PER_MIN = 0.05
BOOST_STALL_MIN = 10

# Product targets and stage params
CAL_TARGET_C = {'Sourdough': 27.0, 'Kombucha': 25.0, 'Water Kefir': 25.0}
STAGE_PARAMS = {
    'Sourdough':   {'startup_air_ceiling': 34.0, 'sample_exit_c': 27.0, 'cooldown_air_safe': 28.5},
    'Kombucha':    {'startup_air_ceiling': 34.0, 'sample_exit_c': 25.0, 'cooldown_air_safe': 27.0},
    'Water Kefir': {'startup_air_ceiling': 34.0, 'sample_exit_c': 25.0, 'cooldown_air_safe': 26.5},
}

# Emergency reverse
EMERGENCY_INSTANT_AIR_C = 36.0
EMERGENCY_SUSTAIN_AIR_C = 34.5
EMERGENCY_SUSTAIN_SEC   = 60

# Paths / files
BASE_DIR_APP = "/home/rpizero/Ferment"
LOG_DIR = os.path.join(BASE_DIR_APP, "logs")
CAL_FILE = os.path.join(BASE_DIR_APP, "calibration_setpoints.json")
os.makedirs(LOG_DIR, exist_ok=True)

# Hardware setup
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2)
button_up=Button(17); button_down=Button(27); button_left=Button(23); button_right=Button(22); button_confirm=Button(26)
motor_pwm = PWMOutputDevice(20); motor_dir = DigitalOutputDevice(21)
fan1 = PWMOutputDevice(12); fan2 = PWMOutputDevice(13)
motor_pwm.value=0.0; fan1.value=0.0; fan2.value=0.0; motor_dir.value=False

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
            show_two_line('Loaded saved','cal setpoints'); time.sleep(1.2)
    except Exception:
        show_two_line('Cal file error','Using defaults'); time.sleep(1.5)

def save_calibration_setpoints(mode_name, low, high):
    data={}
    if os.path.exists(CAL_FILE):
        try:
            with open(CAL_FILE,'r') as f: data=json.load(f)
        except Exception: data={}
    data[mode_name]={'low':round(low,2),'high':round(high,2)}
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

def write_calibration_report(mode,target,stats,decision):
    ts=datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename=f"calibration_{mode.lower().replace(' ','_')}_{ts}.txt"
    path=os.path.join(LOG_DIR,filename)
    with open(path,'w') as f:
        f.write(f'Calibration Report - {mode}\n')
        f.write(f'Timestamp: {datetime.now().isoformat(timespec="seconds")}\n\n')
        f.write(f'Target SAMPLE temperature: {target:.2f} °C\n')
        f.write(f'Window length: {CAL_WINDOW_MIN} minutes\n')
        f.write(f'Early-end stability: {CAL_EARLY_END_STABLE_MIN} min\n')
        f.write(f'Stable window used: last {CAL_STABLE_WINDOW_MIN} min (>= target)\n\n')
        def w(k,v): f.write(f'{k}: {v}\n')
        w('Sample min °C', f'{stats.get("sample_min","--"):.2f}'); w('Sample max °C', f'{stats.get("sample_max","--"):.2f}')
        w('AIR min °C', f'{stats.get("air_min","--"):.2f}');     w('AIR max °C', f'{stats.get("air_max","--"):.2f}')
        w('Stable minutes collected', f'{stats.get("stable_minutes","0.0"):.1f}')
        w('Stable AIR avg °C', f'{stats.get("air_avg","--"):.2f}'); w('Stable SAMPLE avg °C', f'{stats.get("sample_avg","--"):.2f}')
        w('Raw offset (AIR-SAMPLE) °C', f'{stats.get("raw_offset","--"):.2f}')
        w('Safe offset (clamped) °C', f'{stats.get("safe_offset","--"):.2f}')
        w('Raw recommended low/high °C', f'{stats.get("raw_low","--"):.2f} / {stats.get("raw_high","--"):.2f}')
        w('Final recommended low/high °C', f'{stats.get("rec_low","--"):.2f} / {stats.get("rec_high","--"):.2f}')
        w('% time >= target', f'{stats.get("pct_time_at_or_above_target","--"):.1f}%')
        w('Boost slope °C/min (last 10m)', f'{stats.get("boost_slope_c_per_min","--"):.3f}')
        f.write('\nDecision\n')
        for k,v in decision.items():
            f.write(f'- {k}: {v}\n')
        if decision.get('persisted'): f.write('\nPersisted to: calibration_setpoints.json\n')
    return path

def delete_old_cal_reports_for_mode(mode_name: str):
    try:
        key = mode_name.strip().lower().replace(' ', '_')
        for p in Path(LOG_DIR).glob('calibration_*.txt'):
            if p.name.lower().startswith(f'calibration_{key}'):
                try: p.unlink()
                except Exception: pass
    except Exception: pass

def read_temp(sensor_id):
    path=os.path.join(BASE_DIR, sensor_id, 'w1_slave')
    try:
        with open(path) as f: lines=f.readlines()
        if not lines or lines[0].strip().endswith('NO'): return None
        t_pos=lines[1].find('t=')
        if t_pos==-1: return None
        return round(float(lines[1][t_pos+2:])/1000.0,2)
    except: return None

def fans_on(): fan1.value=FAN_SPEED; fan2.value=FAN_SPEED
def fans_off(): fan1.value=0.0; fan2.value=0.0
def cancel_fan_timer():
    global fan_off_timer
    if fan_off_timer: fan_off_timer.cancel(); fan_off_timer=None
def schedule_fan_off(delay=FAN_AFTER_OFF_SEC):
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

def cal_status_display(mode, air, sample, stage):
    stage_map = {"startup":"HOT", "cooldown":"VENT", "hold":"HOLD", "rev":"REV"}
    tag = stage_map.get(stage, "")
    line1 = f"Cal {mode} {tag}"[:16]
    a = "--.-" if air is None else f"{air:.1f}"
    s = "--.-" if sample is None else f"{sample:.1f}"
    line2 = f"A:{a} S:{s}"[:16]
    show_two_line(line1, line2)

def wait_for_button_any():
    while True:
        if button_up.is_pressed: time.sleep(0.2); return 'UP'
        if button_down.is_pressed: time.sleep(0.2); return 'DOWN'
        if button_left.is_pressed: time.sleep(0.2); return 'LEFT'
        if button_right.is_pressed: time.sleep(0.2); return 'RIGHT'
        if button_confirm.is_pressed: time.sleep(0.2); return 'CONFIRM'
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
    global request_pause_menu; request_pause_menu=True
button_left.when_pressed=on_left_pressed

def safe_stop():
    global motor_on
    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_off()
def shutdown_now():
    log=get_log_file(); _write_header_if_needed(log)
    with open(log,'a',newline='') as f: csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'*** SHUTDOWN ***','','','','','','','',''])
    safe_stop(); show_two_line('Shutting down',''); time.sleep(1); subprocess.call(['sudo','shutdown','now'])
def pause_menu():
    sel=select_from_menu(['Resume','Change Mode','Shutdown'],0,True)
    return 'resume' if sel in (None,0) else ('change' if sel==1 else 'shutdown')

def _read_air_and_sample():
    t1=read_temp(SENSORS['Sensor1']); t2=read_temp(SENSORS['Sensor2']); t_sample=read_temp(SENSORS['Sample'])
    air_vals=[t for t in (t1,t2) if t is not None]; air=None if not air_vals else mean(air_vals); tmax=None if not air_vals else max(air_vals)
    return t1,t2,t_sample,air,tmax

def _emergency_reverse_guard(air,high):
    global reversing, motor_on, _overtemp_start_ts
    if air is None: return
    now=time.time()
    if air>=EMERGENCY_INSTANT_AIR_C and not reversing:
        reversing=True; motor_dir.value=not motor_dir.value; motor_pwm.value=1.0; cancel_fan_timer(); fans_on(); _overtemp_start_ts=None; return
    if air>=EMERGENCY_SUSTAIN_AIR_C:
        if _overtemp_start_ts is None: _overtemp_start_ts=now
        elif (now-_overtemp_start_ts)>=EMERGENCY_SUSTAIN_SEC and not reversing:
            reversing=True; motor_dir.value=not motor_dir.value; motor_pwm.value=1.0; cancel_fan_timer(); fans_on(); _overtemp_start_ts=None
    else:
        _overtemp_start_ts=None
    if reversing and air<=(high-1.0):
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
                    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); stage='cooldown'
                else:
                    if (air is not None) and (air>=startup_ceiling):
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                    else:
                        motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
            elif stage=='cooldown':
                motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                if (air is not None) and (air<=cooldown_safe): schedule_fan_off(); stage='hold'
            else:
                if tmax is not None:
                    if motor_on and tmax>high:
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); schedule_fan_off()
                    if (not motor_on) and tmax<=low:
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
    # Require long-press on LEFT to open pause during calibration
    old_left_pressed = button_left.when_pressed
    old_left_held = getattr(button_left, 'when_held', None)
    try:
        try:
            button_left.when_pressed = None
            button_left.hold_time = CAL_PAUSE_LONGPRESS_SEC
            button_left.when_held = on_left_pressed
        except Exception:
            button_left.when_pressed = on_left_pressed
        target=CAL_TARGET_C.get(mode_name,25.0); motor_dir.value=False; motor_on=False; reversing=False; cancel_fan_timer(); fans_off()
        delete_old_cal_reports_for_mode(mode_name)
        maxlen=max(1,int((CAL_WINDOW_MIN*60)/LOOP_INTERVAL_SEC))
        air_buf=deque(maxlen=maxlen); sample_buf=deque(maxlen=maxlen)
        stable_maxlen=max(1,int((CAL_STABLE_WINDOW_MIN*60)/LOOP_INTERVAL_SEC))
        stable_air_buf=deque(maxlen=stable_maxlen); stable_sample_buf=deque(maxlen=stable_maxlen)
        stall_win=max(1,int((BOOST_STALL_MIN*60)/LOOP_INTERVAL_SEC))
        boost_slope_buf=deque(maxlen=stall_win)
        params=STAGE_PARAMS.get(mode_name,STAGE_PARAMS['Sourdough'])
        startup_ceiling=params['startup_air_ceiling']; sample_exit_c=params['sample_exit_c']; cooldown_safe=params['cooldown_air_safe']
        stage='startup'; start_ts=time.time()
        stable_secs=0.0; last_ts=time.time()
        cal_status_display(mode_name, None, None, 'startup')
        while True:
            t1,t2,t_sample,air,tmax=_read_air_and_sample()
            cal_status_display(mode_name, air, t_sample, stage)
            fans_on_state=(fan1.value>0) or (fan2.value>0); log_data(f'CAL-{mode_name}',t1,t2,t_sample,stage,motor_on,motor_dir.value,fans_on_state,reversing)
            _emergency_reverse_guard(air,high)
            if not reversing:
                if stage=='startup':
                    if t_sample is not None:
                        boost_slope_buf.append(t_sample)
                        if len(boost_slope_buf)>=2:
                            dt_min = len(boost_slope_buf)*LOOP_INTERVAL_SEC/60.0
                            dT = boost_slope_buf[-1] - boost_slope_buf[0]
                            slope = dT/dt_min if dt_min>0 else 0.0
                            if slope < BOOST_MIN_RISE_C_PER_MIN and len(boost_slope_buf)==stall_win:
                                motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); stage='cooldown'
                    if (t_sample is not None) and (t_sample>=sample_exit_c):
                        motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); stage='cooldown'
                    else:
                        if (air is not None) and (air>=startup_ceiling):
                            motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                        else:
                            motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
                elif stage=='cooldown':
                    motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on()
                    if (air is not None) and (air<=cooldown_safe): schedule_fan_off(); stage='hold'
                else:
                    if tmax is not None:
                        if motor_on and tmax>high:
                            motor_pwm.value=0.0; motor_on=False; cancel_fan_timer(); fans_on(); schedule_fan_off()
                        if (not motor_on) and tmax<=low:
                            motor_dir.value=False; motor_pwm.value=1.0; motor_on=True; cancel_fan_timer(); fans_on()
            if air is not None: air_buf.append(air)
            if t_sample is not None: sample_buf.append(t_sample)
            now_ts=time.time(); dt=now_ts-last_ts; last_ts=now_ts
            in_band = (t_sample is not None) and (t_sample >= target)
            if in_band:
                stable_secs += dt
                if air is not None: stable_air_buf.append(air)
                if t_sample is not None: stable_sample_buf.append(t_sample)
            elapsed=time.time()-start_ts
            required_stable = max(0, CAL_EARLY_END_STABLE_MIN) * 60
            if finish_requested or elapsed >= CAL_WINDOW_MIN*60 or (CAL_EARLY_END_ENABLED and stable_secs >= required_stable and in_band):
                break
            for _ in range(int(LOOP_INTERVAL_SEC/0.1)):
                if finish_requested: break
                if request_pause_menu:
                    choice=pause_menu()
                    if choice=='resume': request_pause_menu=False; break
                    elif choice=='change': request_pause_menu=False; safe_stop(); return 'change'
                    elif choice=='shutdown': shutdown_now(); return 'shutdown'
                time.sleep(0.1)
            if finish_requested: break
        sample_min=min(sample_buf) if sample_buf else None
        sample_max=max(sample_buf) if sample_buf else None
        air_min=min(air_buf) if air_buf else None
        air_max=max(air_buf) if air_buf else None
        pct_time_at_or_above_target = 0.0
        if sample_buf:
            at_or_above = sum(1 for v in sample_buf if v is not None and v >= target)
            pct_time_at_or_above_target = 100.0 * at_or_above / len(sample_buf)
        stable_minutes = len(stable_sample_buf) * LOOP_INTERVAL_SEC / 60.0
        stats = {
            "sample_min": sample_min if sample_min is not None else float('nan'),
            "sample_max": sample_max if sample_max is not None else float('nan'),
            "air_min": air_min if air_min is not None else float('nan'),
            "air_max": air_max if air_max is not None else float('nan'),
            "stable_minutes": stable_minutes,
            "pct_time_at_or_above_target": pct_time_at_or_above_target,
            "boost_slope_c_per_min": float('nan'),
        }
        decision = {}
        persist_ok = True
        reason = "ok"
        if stable_minutes < CAL_MIN_STABLE_MIN:
            persist_ok = False; reason = f"insufficient stable minutes ({stable_minutes:.1f} < {CAL_MIN_STABLE_MIN})"
        if persist_ok and (sample_max is not None) and (sample_max > (target + 1.0)):
            persist_ok = False; reason = f"sample max {sample_max:.2f} °C too high for {mode_name}"
        rec_low = rec_high = raw_low = raw_high = None
        if persist_ok and len(stable_air_buf)>0 and len(stable_sample_buf)>0:
            air_avg = mean(stable_air_buf); sample_avg = mean(stable_sample_buf)
            raw_offset = air_avg - sample_avg
            safe_offset = min(max(raw_offset, OFFSET_MIN), OFFSET_MAX)
            center = target + safe_offset
            half = RECOMMENDED_BAND_WIDTH/2.0
            raw_low, raw_high = center-half, center+half
            max_high = RECO_MAX_HIGH.get(mode_name, raw_high)
            min_low  = RECO_MIN_LOW.get(mode_name, raw_low)
            rec_low = max(raw_low, min_low)
            rec_high = min(raw_high, max_high)
            clamped = (rec_low != raw_low) or (rec_high != raw_high)
            invalid = (rec_high <= rec_low)
            stats.update({
                "air_avg": air_avg, "sample_avg": sample_avg,
                "raw_offset": raw_offset, "safe_offset": safe_offset,
                "raw_low": raw_low if raw_low is not None else float('nan'),
                "raw_high": raw_high if raw_high is not None else float('nan'),
                "rec_low": rec_low if rec_low is not None else float('nan'),
                "rec_high": rec_high if rec_high is not None else float('nan'),
            })
            if clamped:
                persist_ok = False; reason = f"recommendation clamped to safe bounds ({rec_low:.2f}-{rec_high:.2f})"
            if invalid:
                persist_ok = False; reason = "invalid band (high <= low)"
        else:
            stats.update({
                "air_avg": float('nan'), "sample_avg": float('nan'),
                "raw_offset": float('nan'), "safe_offset": float('nan'),
                "raw_low": float('nan'), "raw_high": float('nan'),
                "rec_low": float('nan'), "rec_high": float('nan'),
            })
        decision["persisted"] = bool(persist_ok)
        decision["reason"] = reason
        report_path = write_calibration_report(mode_name, target, stats, decision)
        log = get_log_file(); _write_header_if_needed(log)
        with open(log,'a',newline='') as f:
            csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f'*** CAL COMPLETE ({mode_name}) ***','','','','','','','',''])
        if persist_ok and rec_low is not None and rec_high is not None:
            save_calibration_setpoints(mode_name, rec_low, rec_high); RANGES[mode_name]=(rec_low,rec_high)
            show_two_line('Cal saved+applied', f'L:{rec_low:.1f} H:{rec_high:.1f}')
        else:
            show_two_line('Cal review needed', 'Kept old setpts')
        time.sleep(2)
        show_two_line('Autostarting...', mode_name[:16]); time.sleep(1)
        return 'autostart'
    finally:
        button_confirm.when_pressed=old
        try:
            button_left.when_pressed = old_left_pressed
            try: button_left.when_held = old_left_held
            except Exception: pass
        except Exception: pass

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
                base=choice.replace('Cal ',''); low,high=RANGES[base]; return ('cal',base,low,high)
            else:
                low,high=RANGES[choice]; return ('mode',choice,low,high)

def main():
    load_calibration_setpoints(); init_log()
    while True:
        sel=main_menu()
        if sel[0]=='shutdown': return
        if sel[0]=='mode':
            _,mode_name,low,high=sel; result=run_mode(mode_name,low,high)
            if result=='shutdown': return
        elif sel[0]=='cal':
            _,mode_name,low,high=sel; result=run_calibration(mode_name,low,high)
            if result=='shutdown': return
            if result=='autostart':
                low, high = RANGES.get(mode_name, (low, high))
                res2 = run_mode(mode_name, low, high)
                if res2=='shutdown': return

if __name__=='__main__': main()
