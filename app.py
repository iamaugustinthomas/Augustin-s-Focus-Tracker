import os
import subprocess
from datetime import datetime, timedelta
import rumps

LOG_FILE = os.path.expanduser("~/Desktop/focus_log.txt")
INTERVAL_SECONDS = 60  # 1 minute checks
RECOVERY_MINUTES = 23  # The 23-minute rule tax

PAUSE_WINDOWS = [
    ("13:00", "14:00"),  # Lunch break
    ("21:00", "05:00")   # Night / Sleep
]
ALLOWED_BREAK_MINUTES_PER_HOUR = 5
MILESTONES = [15, 30, 45, 60, 90, 120]
DISTRACTING_APPS = ["Messages", "WhatsApp", "Music", "Apple Music", "instagram.com", "System Settings", "App Store"]

def play_sound(sound_name):
    try:
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound_name}.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def send_notification(title, subtitle, message):
    as_notification = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
    try:
        subprocess.run(["osascript", "-e", as_notification])
    except:
        pass

def get_active_app():
    cmd = 'tell application "System Events" to get name of first application process whose frontmost is true'
    try:
        proc = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
        return proc.stdout.strip()
    except:
        return "Unknown"

def is_break_time(now):
    current_time_str = now.strftime("%H:%M")
    for start, end in PAUSE_WINDOWS:
        if start <= current_time_str <= end:
            return True, "Scheduled Off-Hours"
    if now.minute < ALLOWED_BREAK_MINUTES_PER_HOUR:
        return True, f"Hourly Recharge Break ({ALLOWED_BREAK_MINUTES_PER_HOUR - now.minute}m left)"
    return False, ""

def ensure_log_exists_and_rotate():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("timestamp,status,points\n")
        return
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        if len(lines) > 5000:
            header = lines[0]
            old_records = lines[1:-1000]
            fresh_records = lines[-1000:]
            archive_path = os.path.expanduser("~/Desktop/focus_log_archive.txt")
            with open(archive_path, "a") as af:
                af.writelines(old_records)
            with open(LOG_FILE, "w") as f:
                f.write(header)
                f.writelines(fresh_records)
    except:
        pass

def get_stats():
    ensure_log_exists_and_rotate()
    daily_pts = 0
    weekly_pts = 0
    last_distraction_time = None
    current_streak = 0
    
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    one_week_ago = now - timedelta(days=7)
    
    with open(LOG_FILE, "r") as f:
        next(f)
        for line in f:
            try:
                ts_str, status, pts_str = line.strip().split(",")
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                pts = int(pts_str)
                
                if ts < one_week_ago:
                    continue
                if ts_str.startswith(today_str):
                    daily_pts += pts
                weekly_pts += pts
                    
                if status == "Yes":
                    current_streak += 1
                elif "No" in status or "Response" in status:
                    current_streak = 0
                    last_distraction_time = ts
            except:
                continue

    multiplier = 1.0 + (min(current_streak, 60) // 15) * 0.5
    multiplier = min(multiplier, 3.0)
    
    in_recovery = False
    minutes_left = 0
    if last_distraction_time:
        time_since_distraction = now - last_distraction_time
        if time_since_distraction < timedelta(minutes=RECOVERY_MINUTES):
            in_recovery = True
            minutes_left = RECOVERY_MINUTES - int(time_since_distraction.total_seconds() / 60)
            
    return daily_pts, weekly_pts, in_recovery, minutes_left, current_streak, multiplier

def log_result(status, pts):
    ensure_log_exists_and_rotate()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts},{status},{pts}\n")

class FocusTrackerApp(rumps.App):
    def __init__(self):
        super(FocusTrackerApp, self).__init__("🧠 Flow", menu=["Today's Points: 0", "Current Streak: 0m", None, "Pause Tracking"])
        self.is_paused = False

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
            log_result(f"Break ({break_reason})", 0)
            return

        d_pts, w_pts, in_recovery, minutes_left, streak, mult = get_stats()
        active_app = get_active_app()
        
        play_sound("Submarine")
        
        app_warning = f" 🚨 (Warning: You are currently on {active_app})" if active_app in DISTRACTING_APPS else ""

        if in_recovery:
            status_msg = f"⚠️ COGNITIVE TAX ACTIVE! ({minutes_left}m remaining)\\nFocus is 80% harder right now.{app_warning}"
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
            proc = subprocess.run(["osascript", "-e", as_script], capture_output=True, text=True)
            output = proc.stdout.strip()
            
            if "gave up:true" in output or "No" in output:
                play_sound("Basso")
                status_logged = f"No (App: {active_app})" if "No" in output else "No Response"
                log_result(status_logged, -230)
            elif "Yes" in output:
                play_sound("Glass")
                log_result("Yes", yes_score)
                
                new_streak = streak + 1
                if new_streak in MILESTONES:
                    send_notification("🔥 FLOW STREAK UPGRADE!", f"Hit {new_streak} Minutes Straight", f"Your multiplier expanded to {1.0 + (min(new_streak, 60) // 15) * 0.5}x!")
                if in_recovery and minutes_left <= 1:
                    send_notification("✨ COGNITIVE TAX LIFTED", "Attention Residue Cleared", "Rewards fully restored!")
        except:
            log_result("Error", 0)

        updated_d_pts, _, _, _, updated_streak, _ = get_stats()
        self.menu["Today's Points: 0"].title = f"Today's Points: {updated_d_pts}"
        self.menu["Current Streak: 0m"].title = f"Current Streak: {updated_streak}m"

if __name__ == "__main__":
    FocusTrackerApp().run()
