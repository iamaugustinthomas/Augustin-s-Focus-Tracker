import os
import subprocess
import webbrowser
import json
from datetime import datetime, timedelta
import rumps

# -------------------------------------------------------------
# Configuration & Constants (Zero Runtime Allocation)
# -------------------------------------------------------------
LOG_FILE = os.path.expanduser("~/Desktop/focus_log.txt")
DASHBOARD_HTML = "/tmp/flow_apple_command_center.html"
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
# Storage-Optimized Reverse Scanner (O(1) RAM)
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
# Zero-Crash Apple Gamified Command Center Generator
# -------------------------------------------------------------
def launch_apple_gamified_gui():
    """
    Scans the last 7 days of telemetry, computes RPG/Apple Fitness metrics,
    writes a hardware-accelerated Apple Glassmorphism HTML5/SVG app to /tmp,
    and opens it natively without touching Python GUI threads.
    """
    ensure_log_initialized()
    d_pts, w_pts, in_recovery, min_left, streak, mult = get_stats_optimized()

    now = datetime.now()
    cutoff_ts = (now - timedelta(days=7)).timestamp()
    today_str = now.strftime("%Y-%m-%d")

    days_list = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(7))]
    day_labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%a") for d in days_list]
    daily_scores = {d: 0 for d in days_list}
    daily_focus_mins = {d: 0 for d in days_list}

    total_xp = 0
    best_streak = 0
    temp_streak = 0
    total_focus_mins = 0
    today_focus_mins = 0
    today_distractions = 0
    total_checks_7d = 0
    focus_checks_7d = 0
    recent_events = []

    try:
        with open(LOG_FILE, "rb") as f:
            f.readline()  # skip header
            for raw_line in f:
                parts = raw_line.strip().split(b",")
                if len(parts) < 3:
                    continue
                try:
                    ts_str = parts[0].decode('ascii')
                    status_str = parts[1].decode('ascii', errors='ignore')
                    pts = int(parts[2])
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                except Exception:
                    continue

                if pts > 0:
                    total_xp += pts
                if status_str == "Yes":
                    temp_streak += 1
                    total_focus_mins += 1
                    if temp_streak > best_streak:
                        best_streak = temp_streak
                elif "No" in status_str or "Response" in status_str:
                    temp_streak = 0

                if ts >= cutoff_ts:
                    d_prefix = ts_str[:10]
                    if d_prefix in daily_scores:
                        daily_scores[d_prefix] += pts
                        if status_str == "Yes":
                            daily_focus_mins[d_prefix] += 1

                    if "Break" not in status_str and status_str != "Error":
                        total_checks_7d += 1
                        if status_str == "Yes":
                            focus_checks_7d += 1

                    if d_prefix == today_str:
                        if status_str == "Yes":
                            today_focus_mins += 1
                        elif "No" in status_str or "Response" in status_str:
                            today_distractions += 1

                    recent_events.append({
                        "time": ts_str[11:16],
                        "date": ts_str[5:10],
                        "status": status_str,
                        "pts": pts
                    })
    except Exception:
        pass

    recent_events = list(reversed(recent_events[-12:]))
    consistency = round((focus_checks_7d / total_checks_7d * 100), 1) if total_checks_7d > 0 else 100.0

    # Gamification Ranks & Levels
    ranks = [
        (0, "Novice Thinker", "🌱"),
        (1000, "Apprentice Mind", "⚡"),
        (3000, "Flow Initiate", "🌊"),
        (7500, "Deep Work Artisan", "🛡️"),
        (15000, "Cognitive Architect", "🧬"),
        (30000, "Neural Grandmaster", "👑"),
        (60000, "Singularity Sovereign", "🌌")
    ]
    current_rank = ranks[0][1]
    rank_icon = ranks[0][2]
    next_rank_xp = 1000
    prev_rank_xp = 0

    for idx, (req_xp, r_name, r_icon) in enumerate(ranks):
        if total_xp >= req_xp:
            current_rank = r_name
            rank_icon = r_icon
            prev_rank_xp = req_xp
            if idx + 1 < len(ranks):
                next_rank_xp = ranks[idx + 1][0]
            else:
                next_rank_xp = total_xp + 10000

    level = (total_xp // 500) + 1
    xp_in_tier = total_xp - prev_rank_xp
    tier_span = max(1, next_rank_xp - prev_rank_xp)
    xp_pct = min(100, round((xp_in_tier / tier_span) * 100, 1))

    # Apple Fitness Ring Percentages
    # Ring 1 (Move/Focus): Goal 180 attentive mins/day
    ring1_pct = min(100, round((today_focus_mins / 180) * 100))
    # Ring 2 (Exercise/Streak): Goal 60m streak
    ring2_pct = min(100, round((streak / 60) * 100))
    # Ring 3 (Stand/Shield): Consistency %
    ring3_pct = min(100, round(consistency))

    # Achievement Badges
    badges = [
        {
            "name": "First Spark",
            "desc": "Log 15+ total focused minutes",
            "icon": "🔥",
            "unlocked": total_focus_mins >= 15
        },
        {
            "name": "Hour of Power",
            "desc": "Hit a 60-minute unbroken streak",
            "icon": "⚡",
            "unlocked": best_streak >= 60
        },
        {
            "name": "3.0x Overclock",
            "desc": "Reach maximum 3.0x Flow Multiplier",
            "icon": "🚀",
            "unlocked": mult >= 3.0 or best_streak >= 60
        },
        {
            "name": "Untouchable",
            "desc": "Zero distractions today (30m+ active)",
            "icon": "🛡️",
            "unlocked": today_focus_mins >= 30 and today_distractions == 0
        },
        {
            "name": "Centurion",
            "desc": "Earn 1,500+ points in a single day",
            "icon": "💎",
            "unlocked": d_pts >= 1500 or max(daily_scores.values() or [0]) >= 1500
        },
        {
            "name": "Deep Immortal",
            "desc": "Accumulate 10,000+ Lifetime XP",
            "icon": "👑",
            "unlocked": total_xp >= 10000
        }
    ]

    scores_array = [daily_scores[d] for d in days_list]
    mins_array = [daily_focus_mins[d] for d in days_list]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flow · Gamified Command Center</title>
<style>
    :root {{
        --bg-dark: #09090d;
        --card-bg: rgba(28, 28, 36, 0.65);
        --card-border: rgba(255, 255, 255, 0.09);
        --text-main: #f5f5f7;
        --text-muted: #86868b;
        --ring-red: #fa114f;
        --ring-green: #a4ff00;
        --ring-cyan: #00f5ea;
        --apple-blue: #0a84ff;
        --apple-purple: #bf5af2;
        --apple-orange: #ff9f0a;
    }}
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
        -webkit-font-smoothing: antialiased;
    }}
    body {{
        background: radial-gradient(circle at 15% 15%, #1a1635 0%, #09090d 55%),
                    radial-gradient(circle at 85% 80%, #0d2538 0%, #09090d 60%);
        background-color: var(--bg-dark);
        color: var(--text-main);
        min-height: 100vh;
        padding: 36px 42px;
    }}
    .container {{
        max-width: 1180px;
        margin: 0 auto;
    }}
    /* Header & Player RPG Banner */
    .hero-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--card-bg);
        backdrop-filter: blur(25px);
        -webkit-backdrop-filter: blur(25px);
        border: 1px solid var(--card-border);
        border-radius: 24px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.45);
    }}
    .player-info {{
        display: flex;
        align-items: center;
        gap: 20px;
    }}
    .avatar-orb {{
        width: 72px;
        height: 72px;
        border-radius: 22px;
        background: linear-gradient(135deg, #0a84ff, #bf5af2, #fa114f);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 36px;
        box-shadow: 0 0 25px rgba(191, 90, 242, 0.45);
    }}
    .rank-badge {{
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        padding: 4px 10px;
        border-radius: 99px;
        background: rgba(191, 90, 242, 0.2);
        color: #e09eff;
        border: 1px solid rgba(191, 90, 242, 0.4);
        margin-bottom: 6px;
    }}
    .player-title {{
        font-size: 28px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }}
    .xp-box {{
        min-width: 320px;
        text-align: right;
    }}
    .xp-labels {{
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        color: var(--text-muted);
        margin-bottom: 8px;
        font-weight: 600;
    }}
    .xp-bar-bg {{
        width: 100%;
        height: 12px;
        background: rgba(255,255,255,0.08);
        border-radius: 99px;
        overflow: hidden;
        position: relative;
    }}
    .xp-bar-fill {{
        height: 100%;
        width: {xp_pct}%;
        background: linear-gradient(90deg, #0a84ff, #bf5af2, #00f5ea);
        border-radius: 99px;
        box-shadow: 0 0 15px rgba(10, 132, 255, 0.7);
        transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
    }}
    /* Status Banner */
    .status-pill {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        font-weight: 600;
        font-size: 14px;
        background: {"rgba(255, 159, 10, 0.14)" if in_recovery else "rgba(48, 209, 88, 0.12)"};
        border: 1px solid {"rgba(255, 159, 10, 0.4)" if in_recovery else "rgba(48, 209, 88, 0.35)"};
        color: {"#ffb340" if in_recovery else "#30d158"};
    }}
    /* Grid Layout */
    .bento-grid {{
        display: grid;
        grid-template-columns: 360px 1fr;
        gap: 24px;
        margin-bottom: 24px;
    }}
    .glass-card {{
        background: var(--card-bg);
        backdrop-filter: blur(25px);
        -webkit-backdrop-filter: blur(25px);
        border: 1px solid var(--card-border);
        border-radius: 24px;
        padding: 26px;
        box-shadow: 0 16px 40px rgba(0,0,0,0.35);
    }}
    .card-heading {{
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--text-muted);
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    /* Concentric Apple Fitness Rings */
    .rings-wrapper {{
        display: flex;
        flex-direction: column;
        align-items: center;
    }}
    .rings-svg-box {{
        position: relative;
        width: 210px;
        height: 210px;
        margin-bottom: 22px;
    }}
    .rings-center-label {{
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        pointer-events: none;
    }}
    .rings-center-label .big-mult {{
        font-size: 28px;
        font-weight: 800;
        background: linear-gradient(135deg, #fff, #a5a5b5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .rings-center-label .sub-mult {{
        font-size: 11px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}
    .ring-legend {{
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }}
    .legend-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
        padding: 8px 12px;
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
    }}
    .dot {{
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
    }}
    /* 4 Mini Stat Capsules inside Right Column */
    .right-col {{
        display: flex;
        flex-direction: column;
        gap: 24px;
    }}
    .kpi-row {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }}
    .kpi-capsule {{
        background: rgba(255,255,255,0.04);
        border: 1px solid var(--card-border);
        border-radius: 18px;
        padding: 16px 18px;
    }}
    .kpi-title {{
        font-size: 11px;
        font-weight: 700;
        color: var(--text-muted);
        text-transform: uppercase;
        margin-bottom: 6px;
    }}
    .kpi-value {{
        font-size: 26px;
        font-weight: 800;
    }}
    /* Bar Chart */
    .chart-box {{
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }}
    .bars-container {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 14px;
        align-items: end;
        height: 190px;
        padding-top: 24px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .bar-col {{
        display: flex;
        flex-direction: column;
        align-items: center;
        height: 100%;
        justify-content: flex-end;
    }}
    .bar-val {{
        font-size: 11px;
        font-weight: 700;
        margin-bottom: 6px;
        color: var(--text-main);
    }}
    .bar-pill {{
        width: 34px;
        border-radius: 10px 10px 4px 4px;
        transition: height 0.6s ease;
        min-height: 6px;
    }}
    .bar-day {{
        margin-top: 10px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
    }}
    /* Bottom Row: Achievements & Live Feed */
    .bottom-grid {{
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        gap: 24px;
    }}
    .badges-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
    }}
    .badge-item {{
        padding: 16px;
        border-radius: 18px;
        border: 1px solid var(--card-border);
        background: rgba(255,255,255,0.03);
        display: flex;
        flex-direction: column;
        gap: 6px;
        transition: transform 0.2s;
    }}
    .badge-item.unlocked {{
        background: linear-gradient(145deg, rgba(10,132,255,0.12), rgba(191,90,242,0.12));
        border-color: rgba(191,90,242,0.45);
        box-shadow: 0 8px 20px rgba(0,0,0,0.25);
    }}
    .badge-item.locked {{
        opacity: 0.35;
        filter: grayscale(100%);
    }}
    .badge-icon {{
        font-size: 28px;
    }}
    .badge-name {{
        font-size: 13px;
        font-weight: 700;
    }}
    .badge-desc {{
        font-size: 11px;
        color: var(--text-muted);
        line-height: 1.35;
    }}
    .feed-list {{
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 230px;
        overflow-y: auto;
    }}
    .feed-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        border-radius: 12px;
        background: rgba(255,255,255,0.03);
        font-size: 13px;
    }}
    .pts-tag {{
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 99px;
        font-size: 12px;
    }}
    .pts-pos {{ background: rgba(48, 209, 88, 0.18); color: #30d158; }}
    .pts-neg {{ background: rgba(255, 69, 58, 0.18); color: #ff453a; }}
    .pts-neu {{ background: rgba(255, 255, 255, 0.1); color: #86868b; }}
</style>
</head>
<body>
<div class="container">
    <!-- Top RPG Player Header -->
    <div class="hero-header">
        <div class="player-info">
            <div class="avatar-orb">{rank_icon}</div>
            <div>
                <span class="rank-badge">LVL {level} · COGNITIVE RANK</span>
                <div class="player-title">{current_rank}</div>
            </div>
        </div>
        <div class="xp-box">
            <div class="xp-labels">
                <span>Lifetime Focus XP</span>
                <span style="color:#fff;">{total_xp:,} / {next_rank_xp:,} XP ({xp_pct}%)</span>
            </div>
            <div class="xp-bar-bg">
                <div class="xp-bar-fill"></div>
            </div>
        </div>
    </div>

    <!-- Live Cognitive Status Banner -->
    <div class="status-pill">
        <span>{"⚠️ COGNITIVE TAX PENALTY ACTIVE — Attention Residue clearing in " + str(min_left) + "m (Points reduced 80%)" if in_recovery else "✨ OPTIMAL NEURAL FLOW ACTIVE — Earning " + str(int(10*mult)) + " pts/min at " + str(mult) + "x Streak Multiplier"}</span>
        <span>Updated {now.strftime("%H:%M:%S")}</span>
    </div>

    <!-- Main Bento Grid -->
    <div class="bento-grid">
        <!-- Apple Fitness Concentric Rings Card -->
        <div class="glass-card rings-wrapper">
            <div class="card-heading" style="width:100%;">
                <span>Activity Rings</span>
                <span>Today</span>
            </div>
            <div class="rings-svg-box">
                <svg width="210" height="210" viewBox="0 0 210 210" style="transform: rotate(-90deg);">
                    <!-- Outer Ring: Focus Mins -->
                    <circle cx="105" cy="105" r="88" stroke="rgba(250, 17, 79, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="88" stroke="var(--ring-red)" stroke-width="16" fill="none"
                            stroke-dasharray="552.9" stroke-dashoffset="{552.9 - (552.9 * ring1_pct / 100):.1f}" stroke-linecap="round"/>
                    <!-- Middle Ring: Streak Target -->
                    <circle cx="105" cy="105" r="68" stroke="rgba(164, 255, 0, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="68" stroke="var(--ring-green)" stroke-width="16" fill="none"
                            stroke-dasharray="427.2" stroke-dashoffset="{427.2 - (427.2 * ring2_pct / 100):.1f}" stroke-linecap="round"/>
                    <!-- Inner Ring: Consistency Shield -->
                    <circle cx="105" cy="105" r="48" stroke="rgba(0, 245, 234, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="48" stroke="var(--ring-cyan)" stroke-width="16" fill="none"
                            stroke-dasharray="301.6" stroke-dashoffset="{301.6 - (301.6 * ring3_pct / 100):.1f}" stroke-linecap="round"/>
                </svg>
                <div class="rings-center-label">
                    <span class="big-mult">{mult}x</span>
                    <span class="sub-mult">Flow Boost</span>
                </div>
            </div>
            <div class="ring-legend">
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-red);"></span>Daily Focus Goal</span>
                    <strong>{today_focus_mins} / 180m ({ring1_pct}%)</strong>
                </div>
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-green);"></span>Flow Streak Ring</span>
                    <strong>{streak} / 60m ({ring2_pct}%)</strong>
                </div>
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-cyan);"></span>7-Day Shield</span>
                    <strong>{consistency}%</strong>
                </div>
            </div>
        </div>

        <!-- Right Column: KPIs + Bar Chart -->
        <div class="right-col">
            <div class="kpi-row">
                <div class="kpi-capsule">
                    <div class="kpi-title">Today's Score</div>
                    <div class="kpi-value" style="color:#0a84ff;">{d_pts:+d}</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">7-Day Score</div>
                    <div class="kpi-value" style="color:#30d158;">{w_pts:+d}</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">Active Streak</div>
                    <div class="kpi-value" style="color:#ff9f0a;">{streak}m</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">All-Time Best</div>
                    <div class="kpi-value" style="color:#bf5af2;">{best_streak}m</div>
                </div>
            </div>

            <div class="glass-card chart-box">
                <div class="card-heading">
                    <span>7-Day Neural Output (Points & Attentive Mins)</span>
                    <span>Peak: {max(scores_array + [0]):+d} pts</span>
                </div>
                <div class="bars-container" id="bars-root"></div>
            </div>
        </div>
    </div>

    <!-- Bottom Grid: Trophy Badges & Recent Telemetry -->
    <div class="bottom-grid">
        <div class="glass-card">
            <div class="card-heading">
                <span>🏆 Gamified Milestones & Badges</span>
                <span>{sum(1 for b in badges if b["unlocked"])} / {len(badges)} Unlocked</span>
            </div>
            <div class="badges-grid" id="badges-root"></div>
        </div>

        <div class="glass-card">
            <div class="card-heading">
                <span>📡 Recent Telemetry Pulses</span>
                <span>Last 12 Checks</span>
            </div>
            <div class="feed-list" id="feed-root"></div>
        </div>
    </div>
</div>

<script>
    const days = {json.dumps(day_labels)};
    const scores = {json.dumps(scores_array)};
    const mins = {json.dumps(mins_array)};
    const badges = {json.dumps(badges)};
    const events = {json.dumps(recent_events)};

    // Render 7-Day Bars
    const maxAbs = Math.max(...scores.map(s => Math.abs(s)), 100);
    const barsRoot = document.getElementById('bars-root');
    scores.forEach((score, i) => {{
        const heightPct = Math.max(8, Math.round((Math.abs(score) / maxAbs) * 135));
        const grad = score >= 0
            ? 'linear-gradient(180deg, #00f5ea, #0a84ff)'
            : 'linear-gradient(180deg, #ff453a, #9e1b12)';
        const col = document.createElement('div');
        col.className = 'bar-col';
        col.innerHTML = `
            <div class="bar-val">${{score >= 0 ? '+' + score : score}}</div>
            <div class="bar-pill" style="height:${{heightPct}}px; background:${{grad}};" title="${{mins[i]}} attentive mins"></div>
            <div class="bar-day">${{days[i]}}</div>
        `;
        barsRoot.appendChild(col);
    }});

    // Render Badges
    const badgesRoot = document.getElementById('badges-root');
    badges.forEach(b => {{
        const el = document.createElement('div');
        el.className = 'badge-item ' + (b.unlocked ? 'unlocked' : 'locked');
        el.innerHTML = `
            <div class="badge-icon">${{b.icon}}</div>
            <div class="badge-name">${{b.name}}</div>
            <div class="badge-desc">${{b.desc}}</div>
        `;
        badgesRoot.appendChild(el);
    }});

    // Render Telemetry Feed
    const feedRoot = document.getElementById('feed-root');
    if (events.length === 0) {{
        feedRoot.innerHTML = '<div style="color:#86868b;font-size:13px;">No focus checks logged yet today.</div>';
    }} else {{
        events.forEach(ev => {{
            const cls = ev.pts > 0 ? 'pts-pos' : (ev.pts < 0 ? 'pts-neg' : 'pts-neu');
            const sign = ev.pts > 0 ? '+' + ev.pts : ev.pts;
            const row = document.createElement('div');
            row.className = 'feed-row';
            row.innerHTML = `
                <span><strong style="color:#fff;">${{ev.time}}</strong> · <span style="color:#86868b;">${{ev.status}}</span></span>
                <span class="pts-tag ${{cls}}">${{sign}} pts</span>
            `;
            feedRoot.appendChild(row);
        }});
    }}
</script>
</body>
</html>"""

    try:
        with open(DASHBOARD_HTML, "w", encoding="utf-8") as f:
            f.write(html_content)
        webbrowser.open(f"file://{DASHBOARD_HTML}")
    except Exception as e:
        rumps.alert("Could not open Command Center", str(e))


# -------------------------------------------------------------
# Menubar App
# -------------------------------------------------------------
class FocusTrackerApp(rumps.App):
    def __init__(self):
        super(FocusTrackerApp, self).__init__(
            "🧠 Flow", 
            menu=[
                "Today's Points: 0", 
                "Current Streak: 0m", 
                None, 
                "🎮 Open Gamified Command Center", 
                "Pause Tracking"
            ]
        )
        self.is_paused = False
        ensure_log_initialized()
        self._refresh_menu_labels()

    def _refresh_menu_labels(self):
        d_pts, _, _, _, streak, mult = get_stats_optimized()
        self.menu["Today's Points: 0"].title = f"🏆 Today: {d_pts:+d} pts ({mult}x)"
        self.menu["Current Streak: 0m"].title = f"🔥 Streak: {streak}m"

    @rumps.clicked("🎮 Open Gamified Command Center")
    def open_command_center(self, _):
        launch_apple_gamified_gui()

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

        self._refresh_menu_labels()


if __name__ == "__main__":
    app = FocusTrackerApp()
    app.run()