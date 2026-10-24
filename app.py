import os
import subprocess
from datetime import datetime, timedelta
import rumps

# -------------------------------------------------------------
# Configuration & Constants (Zero Runtime Allocation)
# -------------------------------------------------------------
LOG_FILE = os.path.expanduser("~/Desktop/focus_log.txt")
INTERVAL_SECONDS = 60  # 1 minute checks
RECOVERY_MINUTES = 23  # The 23-minute rule tax
RECOVERY_SECONDS = RECOVERY_MINUTES * 60

PAUSE_WINDOWS_MINUTES = (
    (13 * 60, 14 * 60),      # 13:00 - 14:00 Lunch
    (21 * 60, 24 * 60),      # 21:00 - 24:00 Night
    (0, 5 * 60)              # 00:00 - 05:00 Early Morning
)
ALLOWED_BREAK_MINUTES_PER_HOUR = 5

DISTRACTING_APPS = frozenset({
    "Messages", "WhatsApp", "Music", "Apple Music", 
    "instagram.com", "System Settings", "App Store"
})
MILESTONES = frozenset({15, 30, 45, 60, 90, 120})

APPLESCRIPT_ACTIVE_APP = [
    'osascript', '-e', 
    'tell application "System Events" to get name of first application process whose frontmost is true'
]

def play_sound(sound_name):
    """Play macOS system audio asynchronously without blocking."""
    try:
        subprocess.Popen(
            ["afplay", f"/System/Library/Sounds/{sound_name}.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def send_notification(title, subtitle, message):
    """Dispatch native macOS banner notification."""
    cmd = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
    try:
        subprocess.Popen(["osascript", "-e", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def get_active_app():
    """Retrieve the frontmost application process name."""
    try:
        proc = subprocess.run(APPLESCRIPT_ACTIVE_APP, capture_output=True, text=True, check=False)
        return proc.stdout.strip()
    except Exception:
        return "Unknown"

def is_break_time(now):
    """Check if current minute falls in configured rest windows."""
    minute_of_day = now.hour * 60 + now.minute
    for start, end in PAUSE_WINDOWS_MINUTES:
        if start <= minute_of_day <= end:
            return True, "Scheduled Off-Hours"
    if now.minute < ALLOWED_BREAK_MINUTES_PER_HOUR:
        return True, f"Hourly Recharge ({ALLOWED_BREAK_MINUTES_PER_HOUR - now.minute}m left)"
    return False, ""

def ensure_log_initialized():
    """Ensure CSV file exists with header."""
    if not os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "wb") as f:
                f.write(b"timestamp,status,points\n")
        except Exception:
            pass

# -------------------------------------------------------------
# Storage-Optimized Reverse Scanner (Reads from end of file)
# -------------------------------------------------------------
def get_stats_optimized():
    ensure_log_initialized()
    daily_pts = 0
    weekly_pts = 0
    last_distraction_ts = 0.0
    current_streak = 0
    streak_active = True

    now = datetime.now()
    now_ts = now.timestamp()
    today_bprefix = now.strftime("%Y-%m-%d").encode('ascii')
    cutoff_ts = (now - timedelta(days=7)).timestamp()

    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_len = f.tell()
            if file_len <= 24:
                return 0, 0, False, 0, 0, 1.0

            buffer_size = 8192
            remaining = file_len
            remainder = b""

            while remaining > 0:
                read_size = min(buffer_size, remaining)
                remaining -= read_size
                f.seek(remaining, os.SEEK_SET)
                chunk = f.read(read_size) + remainder
                lines = chunk.split(b"\n")
                
                if remaining > 0:
                    remainder = lines[0]
                    lines = lines[1:]
                else:
                    remainder = b""

                for line in reversed(lines):
                    line = line.strip()
                    if not line or line.startswith(b"timestamp"):
                        continue

                    parts = line.split(b",")
                    if len(parts) < 3:
                        continue

                    ts_bytes, status_bytes, pts_bytes = parts[0], parts[1], parts[2]
                    try:
                        ts = datetime.strptime(ts_bytes.decode('ascii'), "%Y-%m-%d %H:%M:%S").timestamp()
                    except Exception:
                        continue

                    if ts < cutoff_ts:
                        remaining = 0
                        break

                    try:
                        pts = int(pts_bytes)
                    except Exception:
                        pts = 0

                    if ts_bytes.startswith(today_bprefix):
                        daily_pts += pts
                    weekly_pts += pts

                    if streak_active:
                        if status_bytes == b"Yes":
                            current_streak += 1
                        elif b"No" in status_bytes or b"Response" in status_bytes:
                            streak_active = False
                            if last_distraction_ts == 0.0:
                                last_distraction_ts = ts
                    elif last_distraction_ts == 0.0 and (b"No" in status_bytes or b"Response" in status_bytes):
                        last_distraction_ts = ts
    except Exception:
        pass

    multiplier = min(1.0 + (min(current_streak, 60) // 15) * 0.5, 3.0)
    in_recovery = False
    minutes_left = 0
    if last_distraction_ts > 0.0:
        elapsed = now_ts - last_distraction_ts
        if elapsed < RECOVERY_SECONDS:
            in_recovery = True
            minutes_left = int((RECOVERY_SECONDS - elapsed) // 60) + 1

    return daily_pts, weekly_pts, in_recovery, minutes_left, current_streak, multiplier

def log_result_fast(status: str, pts: int):
    """Direct binary append without encoding overhead."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{now_str},{status},{pts}\n".encode('ascii')
    try:
        with open(LOG_FILE, "ab") as f:
            f.write(entry)
    except Exception:
        pass

# -------------------------------------------------------------
# Menubar App
# -------------------------------------------------------------
class FocusTrackerApp(rumps.App):
    def __init__(self):
        super(FocusTrackerApp, self).__init__(
            "🧠 Flow", 
            menu=["Today's Points: 0", "Current Streak: 0m", None, "Pause Tracking"]
        )
        self.is_paused = False
        ensure_log_initialized()

    @rumps.clicked("Pause Tracking")
    def toggle_tracking_state(self, sender):
        self.is_paused = not self.is_paused
        if self.is_paused:
            sender.title = "Start Tracking"
            self.title = "⏸️ Paused"
        else:
            sender.title = "Pause Tracking"
            self.title = "🧠 Flow"

    @rumps.timer(INTERVAL_SECONDS)
    def focus_check_loop(self, _):
        if self.is_paused:
            return

        now = datetime.now()
        is_break, break_reason = is_break_time(now)
        if is_break:
            log_result_fast(f"Break ({break_reason})", 0)
            return

        d_pts, w_pts, in_recovery, minutes_left, streak, mult = get_stats_optimized()
        active_app = get_active_app()

        play_sound("Submarine")

        app_warning = f" 🚨 (Warning: On {active_app})" if active_app in DISTRACTING_APPS else ""

        if in_recovery:
            status_msg = f"⚠️ COGNITIVE TAX ACTIVE! ({minutes_left}m remaining)\nFocus is 80% harder right now.{app_warning}"
            yes_score = 2
            yes_btn = f"Yes (+{yes_score} Taxed)"
            no_btn = "No (-230 Reset)"
        else:
            yes_score = int(10 * mult)
            status_msg = f"🧠 Optimal Flow Active. Streak: {streak}m (🔥 {mult}x){app_warning}"
            yes_btn = f"Yes (+{yes_score})"
            no_btn = "No (-230)"

        as_script = f'''
        tell application "System Events"
            activate
            set question to "🔥 FOCUS CHECK! 🔥" & return & return & "{status_msg}" & return & return & "🏆 Today's Points: {d_pts}" & return & "📅 This Week's Points: {w_pts}"
            display dialog question buttons {{"{no_btn}", "{yes_btn}"}} default button "{yes_btn}" with title "Cognitive Focus Tracker" giving up after 20
            return result
        end tell
        '''

        try:
            proc = subprocess.run(["osascript", "-e", as_script], capture_output=True, text=True, timeout=25)
            output = proc.stdout.strip()

            if "gave up:true" in output or "No" in output:
                play_sound("Basso")
                status_logged = f"No (App: {active_app})" if "No" in output else "No Response"
                log_result_fast(status_logged, -230)
            elif "Yes" in output:
                play_sound("Glass")
                log_result_fast("Yes", yes_score)

                new_streak = streak + 1
                if new_streak in MILESTONES:
                    send_notification(
                        "🔥 FLOW STREAK UPGRADE!",
                        f"Hit {new_streak} Minutes Straight",
                        f"Multiplier expanded to {1.0 + (min(new_streak, 60) // 15) * 0.5}x!"
                    )
                if in_recovery and minutes_left <= 1:
                    send_notification(
                        "✨ COGNITIVE TAX LIFTED",
                        "Attention Residue Cleared",
                        "Rewards fully restored!"
                    )
        except Exception:
            log_result_fast("Error", 0)

        updated_d_pts, _, _, _, updated_streak, _ = get_stats_optimized()
        self.menu["Today's Points: 0"].title = f"Today's Points: {updated_d_pts}"
        self.menu["Current Streak: 0m"].title = f"Current Streak: {updated_streak}m"


if __name__ == "__main__":
    app = FocusTrackerApp()
    app.run()