import os
import time
from statistics import mean
from datetime import datetime

try:
    import config_local as config  # site-specific overrides (gitignored)
except Exception:
    from . import config  # repo defaults

from .sensors import read_temp
from .io_hw import (
    fans_on, fans_off,
    motor_on_mode_a, motor_reverse_on, motor_off,
    safe_stop, buttons_poll
)
from .logger import log_data
from .ui import show_two_line

# ---- Utilities ----

def _now_str():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def _btn_confirm_pressed(btn_state):
    """
    buttons_poll() is expected to return a mapping of button states.
    We normalize to a single truthy flag for Confirm.
    """
    if not btn_state:
        return False
    # Accept a few common spellings/keys
    for k in ("confirm", "ok", "enter", "select"):
        v = btn_state.get(k)
        if isinstance(v, bool) and v:
            return True
        if isinstance(v, int) and v == 1:
            return True
    return False

def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

# ---- Control helpers (mirror production logic per docs) ----

def _apply_air_control(tmax, low, high, fan_after_off_sec):
    """
    Implements the production AIR-only control:
      - If tmax > High → motor off, fans run-on after off
      - If tmax >= High + 5 → reverse until <= High − 1
      - If tmax <= Low → Mode A (forward), motor on, fans on
    Returns tuple describing hardware state:
      (motor_state: 'off'|'fwd'|'rev', reversing: bool, fans: bool, fan_hold_until: float|None)
    """
    reversing = False
    fans = False
    fan_hold_until = None
    motor_state = 'off'

    if tmax >= (high + 5.0):
        motor_reverse_on()
        fans_on()
        reversing = True
        fans = True
        motor_state = 'rev'
    elif tmax > high:
        # stop motor, start fan run-on window
        motor_off()
        fans_on()
        fans = True
        fan_hold_until = time.monotonic() + float(fan_after_off_sec)
        motor_state = 'off'
    elif tmax <= low:
        motor_on_mode_a()  # forward
        fans_on()
        fans = True
        motor_state = 'fwd'
    else:
        # within band: motor off, fans possibly running due to previous hold
        motor_off()
        motor_state = 'off'
        fans = False

    return motor_state, reversing, fans, fan_hold_until

def _maybe_stop_fans(fan_hold_until):
    if fan_hold_until is None:
        return None
    if time.monotonic() >= fan_hold_until:
        fans_off()
        return None
    return fan_hold_until

# ---- Main calibration ----

def run_calibration(mode_name: str):
    """
    Runs calibration for 'mode_name' for CAL_WINDOW_MIN minutes or until Confirm.
    - Uses AIR sensors only for control decisions.
    - Sample sensor is logged and used only for calibration math.
    - Writes a report: logs/calibration_<mode>_<timestamp>.txt
    - Displays a short summary on the LCD.
    """

    # --- Config & constants (fall back safely if any override missing) ---
    CAL_MIN = int(getattr(config, "CAL_WINDOW_MIN", 120))
    LOOP_SEC = float(getattr(config, "LOOP_SEC", 15.0))
    FAN_AFTER_OFF_SEC = float(getattr(config, "FAN_AFTER_OFF_SEC", 10.0))
    BAND_WIDTH = float(getattr(config, "RECOMMENDED_BAND_WIDTH", 1.0))
    LOG_DIR = getattr(config, "LOG_DIR", "/home/rpizero/Ferment/logs")

    # Per-mode default AIR band and target Sample temp.
    # Your config module likely already has these; we defensively try to read them.
    MODE_AIR_BANDS = getattr(config, "MODE_AIR_BANDS", {
        # fallback examples; replace with your real defaults in config.py
        "Sourdough": (22.0, 26.0),
        "Kombucha": (24.0, 28.0),
        "Water Kefir": (22.0, 27.0),
    })
    TARGET_SAMPLE = getattr(config, "TARGET_SAMPLE_C", {
        # fallback examples; replace with your real defaults in config.py
        "Sourdough": 24.0,
        "Kombucha": 26.0,
        "Water Kefir": 24.0,
    })

    air_low, air_high = MODE_AIR_BANDS.get(mode_name, (22.0, 26.0))
    target_sample = TARGET_SAMPLE.get(mode_name, 24.0)

    SENSOR1 = getattr(config, "SENSOR1_ID", "28-7db6d445e7a7")
    SENSOR2 = getattr(config, "SENSOR2_ID", "28-37e5d44570c3")
    SAMPLE  = getattr(config, "SAMPLE_ID",  "28-3ce1e3800798")

    # --- Buffers for calibration math ---
    air_buf = []
    sample_buf = []

    # --- Timing (robust) ---
    start = time.monotonic()
    deadline = start + CAL_MIN * 60.0

    # --- LCD startup ---
    show_two_line("Calibration", f"{mode_name}  {CAL_MIN} min")
    time.sleep(1.2)

    # Track fan run-on windows across iterations
    fan_hold_until = None

    # --- Main loop ---
    while True:
        t1 = read_temp(SENSOR1)
        t2 = read_temp(SENSOR2)
        ts = read_temp(SAMPLE)

        # Pick max AIR (as per production rule-of-thumb for safety/response)
        air_readings = [t for t in (t1, t2) if t is not None]
        tmax = max(air_readings) if air_readings else None

        # Apply production control policy (AIR-only), collect a possible fan run-on window
        if tmax is not None:
            motor_state, reversing, fans_now, fan_open = _apply_air_control(
                tmax, air_low, air_high, FAN_AFTER_OFF_SEC
            )
            if fan_open is not None:
                # Open/extend a fan hold window
                fan_hold_until = fan_open if (fan_hold_until is None) else max(fan_hold_until, fan_open)
        else:
            # No AIR data → fail safe to motor off, keep fans off unless a hold is active
            motor_off()
            motor_state = 'off'
            reversing = False
            fans_now = False

        # Maintain any active fan hold window
        fan_hold_until = _maybe_stop_fans(fan_hold_until)

        # Log row (even if temps are None; CSV will capture diagnostics)
        log_data(
            mode=f"CAL-{mode_name}",
            t1=t1,
            t2=t2,
            t_sample=ts,
            motor_on=(motor_state != 'off'),
            dir_mode_a=(motor_state == 'fwd'),
            fans_on=(fans_now or (fan_hold_until is not None)),
            reversing=reversing
        )

        # Append to buffers for calibration math (only if values exist)
        if tmax is not None:
            air_buf.append(tmax)
        if ts is not None:
            sample_buf.append(ts)

        # LCD status
        line1 = f"AIR {tmax:.1f}  S {ts:.1f}" if (tmax is not None and ts is not None) else "Reading sensors..."
        # Remaining minutes rounded up for display niceness
        remain_s = max(0.0, deadline - time.monotonic())
        remain_min = int(remain_s // 60.0)
        line2 = f"{mode_name} {remain_min:>3}m  C=Stop"
        show_two_line(line1, line2)

        # Early exit on Confirm
        btns = buttons_poll()
        if _btn_confirm_pressed(btns):
            break

        # End‑time exit
        if time.monotonic() >= deadline:
            break

        # Small, regular cycle delay (non‑blocking for button checks)
        time.sleep(_clamp(LOOP_SEC, 0.5, 60.0))

    # --- End of run: compute results & write report ---
    # Basic guards if data is sparse
    if air_buf and sample_buf:
        air_avg = mean(air_buf)
        sample_avg = mean(sample_buf)
        offset = air_avg - sample_avg  # positive if AIR hotter than Sample

        # Target AIR center to hold the desired Sample
        center_air = target_sample + offset
        half_bw = BAND_WIDTH / 2.0
        rec_low = center_air - half_bw
        rec_high = center_air + half_bw
    else:
        air_avg = sample_avg = offset = center_air = rec_low = rec_high = None

    # Report file
    _ensure_dir(LOG_DIR)
    report_path = os.path.join(LOG_DIR, f"calibration_{mode_name}_{_now_str()}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Mode: {mode_name}\n")
        f.write(f"Window (min): {CAL_MIN}\n")
        f.write(f"Samples (AIR): {len(air_buf)}\n")
        f.write(f"Samples (Sample): {len(sample_buf)}\n")
        if air_avg is not None:
            f.write(f"Average AIR: {air_avg:.3f} C\n")
            f.write(f"Average Sample: {sample_avg:.3f} C\n")
            f.write(f"Offset (AIR - Sample): {offset:.3f} C\n")
            f.write(f"Target Sample: {target_sample:.3f} C\n")
            f.write(f"Recommended center AIR: {center_air:.3f} C\n")
            f.write(f"Recommended Low/High (±{BAND_WIDTH/2:.3f}): {rec_low:.3f} / {rec_high:.3f} C\n")
        else:
            f.write("Insufficient data to compute recommendations.\n")

    # Brief summary on LCD
    if air_avg is not None:
        show_two_line("Cal complete", f"{rec_low:.1f}–{rec_high:.1f} C")
    else:
        show_two_line("Cal complete", "No recommendation")

    # Ensure hardware is safe when leaving
    motor_off()
    fans_off()
    safe_stop()

    return {
        "report": report_path,
        "air_avg": air_avg,
        "sample_avg": sample_avg,
        "offset": offset,
        "recommended": (rec_low, rec_high) if air_avg is not None else None,
    }
