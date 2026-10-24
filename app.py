import os
import subprocess
import webbrowser
import json
import random
from datetime import datetime, timedelta
import rumps

# -------------------------------------------------------------
# Configuration & Constants (Zero Runtime Allocation)
# -------------------------------------------------------------
LOG_FILE = os.path.expanduser("~/Desktop/focus_log.txt")
STATE_FILE = os.path.expanduser("~/Desktop/focus_rpg_state.json")
DASHBOARD_HTML = "/tmp/flow_apple_rpg_center.html"
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
MILESTONES = frozenset({15, 30, 45, 60, 90, 120, 180, 240})

APPLESCRIPT_ACTIVE_APP = [
    'osascript', '-e', 
    'tell application "System Events" to get name of first application process whose frontmost is true'
]

# Daily Bosses Roster (Rotates by Day of Year)
DAILY_BOSSES = [
    {"name": "The Dopamine Leviathan", "hp": 180, "avatar": "🐉", "title": "Devourer of Deep Work"},
    {"name": "Chronos the Time Thief", "hp": 200, "avatar": "⏳", "title": "Master of Procrastination"},
    {"name": "Siren of Infinite Scroll", "hp": 160, "avatar": "🧜‍♀️", "title": "Hypnotist of the Feed"},
    {"name": "The Context-Switch Hydra", "hp": 220, "avatar": "🐍", "title": "Fragmenter of Attention"},
    {"name": "Lord Entropy", "hp": 240, "avatar": "🕳️", "title": "Architect of Chaos"}
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
# Lightweight RPG State Manager (Shields, Crits, Bosses, Quests)
# -------------------------------------------------------------
def load_rpg_state():
    today_str = datetime.now().strftime("%Y-%m-%d")
    default_state = {
        "shields": 1,
        "max_shields": 3,
        "streak_shield_counter": 0,
        "crit_hits_today": 0,
        "loot_Chests_today": 0,
        "shields_saved_today": 0,
        "last_date": today_str,
        "lifetime_crits": 0,
        "lifetime_bosses_slain": 0
    }
    if not os.path.exists(STATE_FILE):
        save_rpg_state(default_state)
        return default_state
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if data.get("last_date") != today_str:
            data["crit_hits_today"] = 0
            data["loot_Chests_today"] = 0
            data["shields_saved_today"] = 0
            data["last_date"] = today_str
            save_rpg_state(data)
        return data
    except Exception:
        return default_state

def save_rpg_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
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
                        if status_bytes.startswith(b"Yes") or b"Shielded" in status_bytes:
                            if status_bytes.startswith(b"Yes"):
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
# Zero-Crash Addictive Apple Gamified Command Center
# -------------------------------------------------------------
def launch_apple_gamified_gui():
    ensure_log_initialized()
    rpg = load_rpg_state()
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
    hourly_heatmap = [0] * 24

    try:
        with open(LOG_FILE, "rb") as f:
            f.readline()
            for raw_line in f:
                parts = raw_line.strip().split(b",")
                if len(parts) < 3:
                    continue
                try:
                    ts_str = parts[0].decode('ascii')
                    status_str = parts[1].decode('ascii', errors='ignore')
                    pts = int(parts[2])
                    dt_obj = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    ts = dt_obj.timestamp()
                except Exception:
                    continue

                if pts > 0:
                    total_xp += pts
                if status_str.startswith("Yes"):
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
                        if status_str.startswith("Yes"):
                            daily_focus_mins[d_prefix] += 1
                            hourly_heatmap[dt_obj.hour] += 1

                    if "Break" not in status_str and status_str != "Error":
                        total_checks_7d += 1
                        if status_str.startswith("Yes") or "Shielded" in status_str:
                            focus_checks_7d += 1

                    if d_prefix == today_str:
                        if status_str.startswith("Yes"):
                            today_focus_mins += 1
                        elif "No" in status_str or "Response" in status_str:
                            today_distractions += 1

                    recent_events.append({
                        "time": ts_str[11:16],
                        "status": status_str,
                        "pts": pts
                    })
    except Exception:
        pass

    recent_events = list(reversed(recent_events[-14:]))
    consistency = round((focus_checks_7d / total_checks_7d * 100), 1) if total_checks_7d > 0 else 100.0

    # Daily Boss Battle Computation
    boss_idx = now.timetuple().tm_yday % len(DAILY_BOSSES)
    boss = DAILY_BOSSES[boss_idx]
    boss_max_hp = boss["hp"]
    boss_rem_hp = max(0, boss_max_hp - today_focus_mins)
    boss_hp_pct = round((boss_rem_hp / boss_max_hp) * 100, 1)
    boss_slain = boss_rem_hp == 0

    # Daily Quests (Auto-tracked)
    quests = [
        {
            "title": "Ignition Sequence",
            "desc": "Reach a 30-minute unbroken streak",
            "prog": min(30, max(streak, best_streak if today_focus_mins > 0 else 0)),
            "goal": 30,
            "reward": "+250 XP",
            "done": streak >= 30 or today_focus_mins >= 30
        },
        {
            "title": "Deep Work Marathon",
            "desc": "Accumulate 120 attentive minutes today",
            "prog": min(120, today_focus_mins),
            "goal": 120,
            "reward": "+500 XP",
            "done": today_focus_mins >= 120
        },
        {
            "title": "Critical Overdrive",
            "desc": "Trigger 3 Critical Focus Hits today",
            "prog": min(3, rpg.get("crit_hits_today", 0)),
            "goal": 3,
            "reward": "+300 XP",
            "done": rpg.get("crit_hits_today", 0) >= 3
        },
        {
            "title": "Slay the Daily Boss",
            "desc": f"Deplete {boss['name']}'s HP to 0",
            "prog": min(boss_max_hp, today_focus_mins),
            "goal": boss_max_hp,
            "reward": "🏆 Boss Trophy",
            "done": boss_slain
        }
    ]

    # Add Quest Bonus XP
    quest_bonus = sum(300 for q in quests if q["done"])
    total_xp += quest_bonus

    # RPG Level & Prestige Rank
    ranks = [
        (0, "Novice Thinker", "🌱"),
        (1000, "Dopamine Tamer", "⚡"),
        (3500, "Flow Initiate", "🌊"),
        (8000, "Deep Work Ronin", "⚔️"),
        (16000, "Cognitive Vanguard", "🛡️"),
        (32000, "Neural Warlock", "🧬"),
        (64000, "Time-Bending Titan", "⏳"),
        (120000, "Singularity Sovereign", "🌌")
    ]
    current_rank, rank_icon = ranks[0][1], ranks[0][2]
    next_rank_xp, prev_rank_xp = 1000, 0

    for idx, (req_xp, r_name, r_icon) in enumerate(ranks):
        if total_xp >= req_xp:
            current_rank, rank_icon, prev_rank_xp = r_name, r_icon, req_xp
            next_rank_xp = ranks[idx + 1][0] if idx + 1 < len(ranks) else total_xp + 25000

    level = (total_xp // 500) + 1
    xp_in_tier = total_xp - prev_rank_xp
    tier_span = max(1, next_rank_xp - prev_rank_xp)
    xp_pct = min(100, round((xp_in_tier / tier_span) * 100, 1))

    # Apple Fitness Rings
    ring1_pct = min(100, round((today_focus_mins / 180) * 100))
    ring2_pct = min(100, round((streak / 60) * 100))
    ring3_pct = min(100, round(consistency))

    shields_count = rpg.get("shields", 1)
    shield_progress = rpg.get("streak_shield_counter", 0)
    shields_display = "🛡️" * shields_count + "⚫" * (3 - shields_count)

    # Unlockable Achievements
    badges = [
        {"name": "First Blood", "desc": "Deal 15m damage to a Daily Boss", "icon": "🗡️", "unlocked": total_focus_mins >= 15},
        {"name": "Godlike Streak", "desc": "Hit a 60m unbroken flow streak", "icon": "🔥", "unlocked": best_streak >= 60},
        {"name": "Lucky Seven", "desc": "Land a 5x Legendary Loot Jackpot", "icon": "🎰", "unlocked": rpg.get("loot_Chests_today", 0) > 0 or total_xp >= 2500},
        {"name": "Aegis Immortal", "desc": "Block a distraction with a Streak Shield", "icon": "🛡️", "unlocked": rpg.get("shields_saved_today", 0) > 0 or shields_count >= 2},
        {"name": "Boss Slayer", "desc": "Defeat a Daily Boss (100% HP depleted)", "icon": "💀", "unlocked": boss_slain or best_streak >= 90},
        {"name": "Apex Mind", "desc": "Pass 15,000+ Lifetime Focus XP", "icon": "👑", "unlocked": total_xp >= 15000}
    ]

    scores_array = [daily_scores[d] for d in days_list]
    mins_array = [daily_focus_mins[d] for d in days_list]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Flow · Gamified Neural Arena</title>
<style>
    :root {{
        --bg-dark: #07070b;
        --card-bg: rgba(24, 24, 34, 0.72);
        --card-border: rgba(255, 255, 255, 0.09);
        --text-main: #f5f5f7;
        --text-muted: #86868b;
        --ring-red: #fa114f;
        --ring-green: #a4ff00;
        --ring-cyan: #00f5ea;
        --apple-blue: #0a84ff;
        --apple-purple: #bf5af2;
        --apple-orange: #ff9f0a;
        --apple-gold: #ffd60a;
    }}
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
        -webkit-font-smoothing: antialiased;
    }}
    body {{
        background: radial-gradient(circle at 10% 10%, #241445 0%, #07070b 50%),
                    radial-gradient(circle at 90% 85%, #0c2b40 0%, #07070b 55%);
        background-color: var(--bg-dark);
        color: var(--text-main);
        min-height: 100vh;
        padding: 32px 38px;
    }}
    .container {{ max-width: 1220px; margin: 0 auto; }}

    /* Top RPG Player Bar */
    .hero-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--card-bg);
        backdrop-filter: blur(30px);
        border: 1px solid var(--card-border);
        border-radius: 24px;
        padding: 22px 30px;
        margin-bottom: 20px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
    }}
    .player-info {{ display: flex; align-items: center; gap: 18px; }}
    .avatar-orb {{
        width: 74px; height: 74px; border-radius: 22px;
        background: linear-gradient(135deg, #0a84ff, #bf5af2, #fa114f);
        display: flex; align-items: center; justify-content: center;
        font-size: 38px;
        box-shadow: 0 0 30px rgba(191, 90, 242, 0.55);
    }}
    .rank-badge {{
        display: inline-block; font-size: 11px; font-weight: 800;
        text-transform: uppercase; letter-spacing: 1.2px;
        padding: 4px 10px; border-radius: 99px;
        background: rgba(255, 214, 10, 0.15); color: var(--apple-gold);
        border: 1px solid rgba(255, 214, 10, 0.4); margin-bottom: 6px;
    }}
    .player-title {{ font-size: 28px; font-weight: 800; letter-spacing: -0.5px; }}
    .shield-box {{
        background: rgba(255,255,255,0.04);
        border: 1px solid var(--card-border);
        padding: 12px 20px;
        border-radius: 18px;
        text-align: center;
    }}
    .shield-icons {{ font-size: 22px; letter-spacing: 4px; margin-bottom: 4px; }}
    .shield-sub {{ font-size: 11px; color: var(--text-muted); font-weight: 600; }}

    .xp-box {{ min-width: 320px; text-align: right; }}
    .xp-labels {{
        display: flex; justify-content: space-between;
        font-size: 13px; color: var(--text-muted);
        margin-bottom: 8px; font-weight: 700;
    }}
    .xp-bar-bg {{
        width: 100%; height: 13px; background: rgba(255,255,255,0.08);
        border-radius: 99px; overflow: hidden;
    }}
    .xp-bar-fill {{
        height: 100%; width: {xp_pct}%;
        background: linear-gradient(90deg, #0a84ff, #bf5af2, #00f5ea);
        border-radius: 99px;
        box-shadow: 0 0 18px rgba(0, 245, 234, 0.7);
    }}

    /* Boss Battle Banner */
    .boss-card {{
        background: linear-gradient(135deg, rgba(45, 14, 30, 0.8), rgba(20, 20, 32, 0.85));
        border: 1px solid rgba(250, 17, 79, 0.35);
        border-radius: 24px;
        padding: 20px 28px;
        margin-bottom: 22px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        box-shadow: 0 15px 40px rgba(250, 17, 79, 0.15);
    }}
    .boss-left {{ display: flex; align-items: center; gap: 18px; }}
    .boss-avatar {{
        font-size: 44px;
        width: 68px; height: 68px;
        background: rgba(250, 17, 79, 0.15);
        border: 1px solid rgba(250, 17, 79, 0.4);
        border-radius: 20px;
        display: flex; align-items: center; justify-content: center;
    }}
    .boss-tag {{
        font-size: 10px; font-weight: 800; text-transform: uppercase;
        letter-spacing: 1.4px; color: #ff453a;
    }}
    .boss-name {{ font-size: 22px; font-weight: 800; }}
    .boss-hp-wrap {{ flex: 1; max-width: 520px; }}
    .boss-hp-top {{
        display: flex; justify-content: space-between;
        font-size: 12px; font-weight: 700; margin-bottom: 8px;
    }}
    .boss-hp-bar {{
        width: 100%; height: 16px; background: rgba(0,0,0,0.45);
        border-radius: 99px; overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
    }}
    .boss-hp-fill {{
        height: 100%; width: {boss_hp_pct}%;
        background: linear-gradient(90deg, #ff453a, #ff9f0a);
        box-shadow: 0 0 15px rgba(255, 69, 58, 0.6);
        transition: width 0.8s ease;
    }}

    /* Main Grid */
    .bento-grid {{
        display: grid;
        grid-template-columns: 350px 1fr;
        gap: 22px;
        margin-bottom: 22px;
    }}
    .glass-card {{
        background: var(--card-bg);
        backdrop-filter: blur(25px);
        border: 1px solid var(--card-border);
        border-radius: 24px;
        padding: 24px;
        box-shadow: 0 16px 40px rgba(0,0,0,0.35);
    }}
    .card-heading {{
        font-size: 12px; font-weight: 800; text-transform: uppercase;
        letter-spacing: 1.1px; color: var(--text-muted);
        margin-bottom: 18px; display: flex; justify-content: space-between;
    }}

    /* Rings */
    .rings-wrapper {{ display: flex; flex-direction: column; align-items: center; }}
    .rings-svg-box {{ position: relative; width: 200px; height: 200px; margin-bottom: 18px; }}
    .rings-center-label {{
        position: absolute; inset: 0;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
    }}
    .big-mult {{
        font-size: 30px; font-weight: 900;
        color: {"#ffd60a" if mult >= 2.5 else "#fff"};
        text-shadow: 0 0 18px rgba(255, 214, 10, 0.4);
    }}
    .sub-mult {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; }}
    .ring-legend {{ width: 100%; display: flex; flex-direction: column; gap: 9px; }}
    .legend-row {{
        display: flex; justify-content: space-between; font-size: 13px;
        padding: 8px 12px; background: rgba(255,255,255,0.03); border-radius: 10px;
    }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px; }}

    .right-col {{ display: flex; flex-direction: column; gap: 22px; }}
    .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .kpi-capsule {{
        background: rgba(255,255,255,0.04); border: 1px solid var(--card-border);
        border-radius: 18px; padding: 15px 18px;
    }}
    .kpi-title {{ font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }}
    .kpi-value {{ font-size: 25px; font-weight: 800; }}

    /* Bars */
    .bars-container {{
        display: grid; grid-template-columns: repeat(7, 1fr);
        gap: 14px; align-items: end; height: 175px;
        padding-top: 20px; border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .bar-col {{ display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }}
    .bar-val {{ font-size: 11px; font-weight: 700; margin-bottom: 6px; }}
    .bar-pill {{ width: 34px; border-radius: 10px 10px 4px 4px; min-height: 6px; }}
    .bar-day {{ margin-top: 8px; font-size: 12px; font-weight: 600; color: var(--text-muted); }}

    /* Quests & Badges Row */
    .bottom-grid {{ display: grid; grid-template-columns: 1fr 1.1fr 0.9fr; gap: 22px; }}
    .quest-list {{ display: flex; flex-direction: column; gap: 12px; }}
    .quest-item {{
        background: rgba(255,255,255,0.03); border: 1px solid var(--card-border);
        padding: 12px 14px; border-radius: 14px;
    }}
    .quest-item.done {{
        border-color: rgba(48, 209, 88, 0.5);
        background: rgba(48, 209, 88, 0.08);
    }}
    .quest-top {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; margin-bottom: 4px; }}
    .quest-desc {{ font-size: 11px; color: var(--text-muted); margin-bottom: 8px; }}
    .quest-bar-bg {{ height: 6px; background: rgba(255,255,255,0.08); border-radius: 99px; overflow: hidden; }}
    .quest-bar-fill {{ height: 100%; background: linear-gradient(90deg, #30d158, #00f5ea); }}

    .badges-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .badge-item {{
        padding: 13px; border-radius: 16px; border: 1px solid var(--card-border);
        background: rgba(255,255,255,0.03); display: flex; align-items: center; gap: 12px;
    }}
    .badge-item.unlocked {{
        background: linear-gradient(145deg, rgba(10,132,255,0.14), rgba(191,90,242,0.14));
        border-color: rgba(191,90,242,0.45);
    }}
    .badge-item.locked {{ opacity: 0.3; filter: grayscale(100%); }}
    .badge-icon {{ font-size: 26px; }}
    .badge-name {{ font-size: 13px; font-weight: 700; }}
    .badge-desc {{ font-size: 11px; color: var(--text-muted); }}

    .feed-list {{ display: flex; flex-direction: column; gap: 8px; max-height: 290px; overflow-y: auto; }}
    .feed-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 9px 12px; border-radius: 11px; background: rgba(255,255,255,0.03); font-size: 12px;
    }}
    .pts-tag {{ font-weight: 700; padding: 3px 8px; border-radius: 99px; font-size: 11px; }}
    .pts-pos {{ background: rgba(48, 209, 88, 0.18); color: #30d158; }}
    .pts-crit {{ background: rgba(255, 214, 10, 0.22); color: #ffd60a; border: 1px solid rgba(255,214,10,0.4); }}
    .pts-neg {{ background: rgba(255, 69, 58, 0.18); color: #ff453a; }}
    .pts-neu {{ background: rgba(255, 255, 255, 0.1); color: #86868b; }}
</style>
</head>
<body>
<div class="container">
    <!-- Top RPG Header -->
    <div class="hero-header">
        <div class="player-info">
            <div class="avatar-orb">{rank_icon}</div>
            <div>
                <span class="rank-badge">LVL {level} · PRESTIGE CLASS</span>
                <div class="player-title">{current_rank}</div>
            </div>
        </div>

        <div class="shield-box" title="Every 45m of unbroken focus forges 1 Aegis Shield. Automatically blocks a -230 distraction penalty!">
            <div class="shield-icons">{shields_display}</div>
            <div class="shield-sub">AEGIS STREAK SHIELDS ({shield_progress}/45m to next)</div>
        </div>

        <div class="xp-box">
            <div class="xp-labels">
                <span>Total Neural XP</span>
                <span style="color:#fff;">{total_xp:,} / {next_rank_xp:,} XP ({xp_pct}%)</span>
            </div>
            <div class="xp-bar-bg"><div class="xp-bar-fill"></div></div>
        </div>
    </div>

    <!-- Daily Boss Battle Arena -->
    <div class="boss-card">
        <div class="boss-left">
            <div class="boss-avatar">{boss["avatar"]}</div>
            <div>
                <div class="boss-tag">⚔️ DAILY BOSS ENCOUNTER · {boss["title"]}</div>
                <div class="boss-name">{boss["name"]} {"(SLAIN! 🏆)" if boss_slain else ""}</div>
            </div>
        </div>
        <div class="boss-hp-wrap">
            <div class="boss-hp-top">
                <span style="color:#ff9f0a;">Each Focused Minute = -1 Boss HP</span>
                <span>{boss_rem_hp} / {boss_max_hp} HP ({boss_hp_pct}%)</span>
            </div>
            <div class="boss-hp-bar"><div class="boss-hp-fill"></div></div>
        </div>
    </div>

    <!-- Main Bento Grid -->
    <div class="bento-grid">
        <div class="glass-card rings-wrapper">
            <div class="card-heading" style="width:100%;">
                <span>Neural Rings</span>
                <span>{"🔥 FEVER MODE" if mult >= 2.5 else "Active"}</span>
            </div>
            <div class="rings-svg-box">
                <svg width="200" height="200" viewBox="0 0 210 210" style="transform: rotate(-90deg);">
                    <circle cx="105" cy="105" r="88" stroke="rgba(250, 17, 79, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="88" stroke="var(--ring-red)" stroke-width="16" fill="none"
                            stroke-dasharray="552.9" stroke-dashoffset="{552.9 - (552.9 * ring1_pct / 100):.1f}" stroke-linecap="round"/>
                    <circle cx="105" cy="105" r="68" stroke="rgba(164, 255, 0, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="68" stroke="var(--ring-green)" stroke-width="16" fill="none"
                            stroke-dasharray="427.2" stroke-dashoffset="{427.2 - (427.2 * ring2_pct / 100):.1f}" stroke-linecap="round"/>
                    <circle cx="105" cy="105" r="48" stroke="rgba(0, 245, 234, 0.18)" stroke-width="16" fill="none"/>
                    <circle cx="105" cy="105" r="48" stroke="var(--ring-cyan)" stroke-width="16" fill="none"
                            stroke-dasharray="301.6" stroke-dashoffset="{301.6 - (301.6 * ring3_pct / 100):.1f}" stroke-linecap="round"/>
                </svg>
                <div class="rings-center-label">
                    <span class="big-mult">{mult}x</span>
                    <span class="sub-mult">Combo Mult</span>
                </div>
            </div>
            <div class="ring-legend">
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-red);"></span>Daily Focus Ring</span>
                    <strong>{today_focus_mins} / 180m ({ring1_pct}%)</strong>
                </div>
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-green);"></span>Combo Streak</span>
                    <strong>{streak} / 60m ({ring2_pct}%)</strong>
                </div>
                <div class="legend-row">
                    <span><span class="dot" style="background:var(--ring-cyan);"></span>Consistency Shield</span>
                    <strong>{consistency}%</strong>
                </div>
            </div>
        </div>

        <div class="right-col">
            <div class="kpi-row">
                <div class="kpi-capsule">
                    <div class="kpi-title">Today's Score</div>
                    <div class="kpi-value" style="color:#0a84ff;">{d_pts:+d}</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">Crit Drops Today</div>
                    <div class="kpi-value" style="color:#ffd60a;">⚡ {rpg.get("crit_hits_today", 0)}</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">Active Streak</div>
                    <div class="kpi-value" style="color:#30d158;">🔥 {streak}m</div>
                </div>
                <div class="kpi-capsule">
                    <div class="kpi-title">All-Time Record</div>
                    <div class="kpi-value" style="color:#bf5af2;">👑 {best_streak}m</div>
                </div>
            </div>

            <div class="glass-card" style="flex:1; display:flex; flex-direction:column; justify-content:space-between;">
                <div class="card-heading">
                    <span>7-Day Neural Output</span>
                    <span>7-Day Total: {w_pts:+d} XP</span>
                </div>
                <div class="bars-container" id="bars-root"></div>
            </div>
        </div>
    </div>

    <!-- Bottom Grid: Quests, Achievements, Live Combat Log -->
    <div class="bottom-grid">
        <div class="glass-card">
            <div class="card-heading">
                <span>📜 Daily Bounties & Quests</span>
                <span>{sum(1 for q in quests if q["done"])}/4 Done</span>
            </div>
            <div class="quest-list" id="quests-root"></div>
        </div>

        <div class="glass-card">
            <div class="card-heading">
                <span>🏆 Prestige Trophies</span>
                <span>{sum(1 for b in badges if b["unlocked"])}/{len(badges)}</span>
            </div>
            <div class="badges-grid" id="badges-root"></div>
        </div>

        <div class="glass-card">
            <div class="card-heading">
                <span>⚡ Live Combat & Loot Log</span>
                <span>Last 14</span>
            </div>
            <div class="feed-list" id="feed-root"></div>
        </div>
    </div>
</div>

<script>
    const days = {json.dumps(day_labels)};
    const scores = {json.dumps(scores_array)};
    const mins = {json.dumps(mins_array)};
    const quests = {json.dumps(quests)};
    const badges = {json.dumps(badges)};
    const events = {json.dumps(recent_events)};

    // Bars
    const maxAbs = Math.max(...scores.map(s => Math.abs(s)), 100);
    const barsRoot = document.getElementById('bars-root');
    scores.forEach((score, i) => {{
        const heightPct = Math.max(8, Math.round((Math.abs(score) / maxAbs) * 125));
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

    // Quests
    const questsRoot = document.getElementById('quests-root');
    quests.forEach(q => {{
        const pct = Math.min(100, Math.round((q.prog / q.goal) * 100));
        const item = document.createElement('div');
        item.className = 'quest-item ' + (q.done ? 'done' : '');
        item.innerHTML = `
            <div class="quest-top">
                <span>${{q.done ? '✅ ' : '🎯 '}}${{q.title}}</span>
                <span style="color:#ffd60a;">${{q.reward}}</span>
            </div>
            <div class="quest-desc">${{q.desc}} (${{q.prog}}/${{q.goal}})</div>
            <div class="quest-bar-bg"><div class="quest-bar-fill" style="width:${{pct}}%;"></div></div>
        `;
        questsRoot.appendChild(item);
    }});

    // Badges
    const badgesRoot = document.getElementById('badges-root');
    badges.forEach(b => {{
        const el = document.createElement('div');
        el.className = 'badge-item ' + (b.unlocked ? 'unlocked' : 'locked');
        el.innerHTML = `
            <div class="badge-icon">${{b.icon}}</div>
            <div>
                <div class="badge-name">${{b.name}}</div>
                <div class="badge-desc">${{b.desc}}</div>
            </div>
        `;
        badgesRoot.appendChild(el);
    }});

    // Feed
    const feedRoot = document.getElementById('feed-root');
    events.forEach(ev => {{
        const isCrit = ev.status.includes('CRIT') || ev.status.includes('JACKPOT');
        const cls = isCrit ? 'pts-crit' : (ev.pts > 0 ? 'pts-pos' : (ev.pts < 0 ? 'pts-neg' : 'pts-neu'));
        const sign = ev.pts > 0 ? '+' + ev.pts : ev.pts;
        const row = document.createElement('div');
        row.className = 'feed-row';
        row.innerHTML = `
            <span><strong style="color:#fff;">${{ev.time}}</strong> · <span style="color:#a0a0ab;">${{ev.status}}</span></span>
            <span class="pts-tag ${{cls}}">${{sign}} XP</span>
        `;
        feedRoot.appendChild(row);
    }});
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
# Addictive RPG Menubar App
# -------------------------------------------------------------
class FocusTrackerApp(rumps.App):
    def __init__(self):
        super(FocusTrackerApp, self).__init__(
            "🧠 Flow", 
            menu=[
                "Today's Points: 0", 
                "Current Streak: 0m",
                "Aegis Shields: 🛡️",
                None, 
                "🎮 Open Gamified Command Center", 
                "Pause Tracking"
            ]
        )
        self.is_paused = False
        ensure_log_initialized()
        self._refresh_menu_labels()

    def _refresh_menu_labels(self):
        rpg = load_rpg_state()
        d_pts, _, _, _, streak, mult = get_stats_optimized()
        shields = rpg.get("shields", 1)
        shield_str = "🛡️" * shields + "⚫" * (3 - shields)

        # Dynamic menubar title shows streak & fever state
        if not self.is_paused:
            if streak >= 60:
                self.title = f"🔥 {streak}m (3x)"
            elif streak >= 15:
                self.title = f"⚡ {streak}m ({mult}x)"
            else:
                self.title = f"🧠 {d_pts:+d}"

        self.menu["Today's Points: 0"].title = f"🏆 Today: {d_pts:+d} XP ({mult}x)"
        self.menu["Current Streak: 0m"].title = f"🔥 Streak: {streak}m"
        self.menu["Aegis Shields: 🛡️"].title = f"🛡️ Shields: {shield_str} ({rpg.get('streak_shield_counter',0)}/45m)"

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
            self._refresh_menu_labels()

    @rumps.timer(INTERVAL_SECONDS)
    def focus_check_loop(self, _):
        if self.is_paused:
            return

        now = datetime.now()
        is_break, break_reason = is_break_time(now)
        if is_break:
            log_result_fast(f"Break ({break_reason})", 0)
            return

        rpg = load_rpg_state()
        d_pts, w_pts, in_recovery, minutes_left, streak, mult = get_stats_optimized()
        active_app = get_active_app()

        play_sound("Submarine")

        shields_avail = rpg.get("shields", 0)
        shield_badge = "🛡️" * shields_avail if shields_avail > 0 else "None"
        app_warning = f"\n🚨 Warning: Active on {active_app}!" if active_app in DISTRACTING_APPS else ""

        if in_recovery:
            base_score = 2
            status_msg = f"⚠️ COGNITIVE TAX ACTIVE ({minutes_left}m left)\nRewards reduced 80%.{app_warning}"
            yes_btn = f"Yes (+{base_score} XP)"
            no_btn = "Use Shield 🛡️" if shields_avail > 0 else "No (-230 XP)"
        else:
            base_score = int(10 * mult)
            status_msg = f"⚡ COMBO: {streak}m (🔥 {mult}x Multiplier)\n🛡️ Aegis Shields: {shield_badge}{app_warning}"
            yes_btn = f"Yes (+{base_score} XP + Loot Roll)"
            no_btn = "Block w/ Shield 🛡️" if shields_avail > 0 else "No (-230 Reset)"

        as_script = f'''
        tell application "System Events"
            activate
            set question to "⚔️ NEURAL FOCUS CHECK ⚔️" & return & return & "{status_msg}" & return & return & "🏆 Today: {d_pts} XP   |   📅 Week: {w_pts} XP"
            display dialog question buttons {{"{no_btn}", "{yes_btn}"}} default button "{yes_btn}" with title "Flow RPG Arena" giving up after 20
            return result
        end tell
        '''

        try:
            proc = subprocess.run(["osascript", "-e", as_script], capture_output=True, text=True, timeout=25)
            output = proc.stdout.strip()

            if "gave up:true" in output or "No" in output or "Block" in output or "Shield" in output:
                # Check if player has an Aegis Shield to block the distraction penalty!
                if shields_avail > 0:
                    rpg["shields"] = shields_avail - 1
                    rpg["shields_saved_today"] = rpg.get("shields_saved_today", 0) + 1
                    save_rpg_state(rpg)
                    play_sound("Tink")
                    log_result_fast(f"Shielded ({active_app})", 0)
                    send_notification(
                        "🛡️ AEGIS SHIELD ACTIVATED!",
                        f"Streak of {streak}m Saved!",
                        f"Blocked -230 XP penalty! ({rpg['shields']} shields left)"
                    )
                else:
                    rpg["streak_shield_counter"] = 0
                    save_rpg_state(rpg)
                    play_sound("Basso")
                    status_logged = f"No (App: {active_app})" if "No" in output else "No Response"
                    log_result_fast(status_logged, -230)
            elif "Yes" in output:
                # Variable Ratio Dopamine Roll (Crit / Legendary Chest)
                roll = random.random()
                final_score = base_score
                status_tag = "Yes"

                if not in_recovery and roll < 0.03:
                    # 3% Legendary Chest (5x)
                    final_score = base_score * 5
                    status_tag = "Yes (🎰 5x JACKPOT!)"
                    rpg["loot_Chests_today"] = rpg.get("loot_Chests_today", 0) + 1
                    rpg["crit_hits_today"] = rpg.get("crit_hits_today", 0) + 1
                    play_sound("Hero")
                    send_notification("🎰 LEGENDARY LOOT CHEST!", f"+{final_score} XP JACKPOT!", "5x Multiplier Roll Landed!")
                elif not in_recovery and roll < 0.15:
                    # 12% Critical Hit (2x)
                    final_score = base_score * 2
                    status_tag = "Yes (⚡ 2x CRIT!)"
                    rpg["crit_hits_today"] = rpg.get("crit_hits_today", 0) + 1
                    play_sound("Funk")
                    send_notification("⚡ CRITICAL FOCUS HIT!", f"+{final_score} XP (2x CritBonus)!", "Dopamine surge active!")
                else:
                    play_sound("Glass")

                # Increment Shield Forge Counter
                rpg["streak_shield_counter"] = rpg.get("streak_shield_counter", 0) + 1
                if rpg["streak_shield_counter"] >= 45:
                    rpg["streak_shield_counter"] = 0
                    if rpg.get("shields", 0) < 3:
                        rpg["shields"] = rpg.get("shields", 0) + 1
                        play_sound("Hero")
                        send_notification(
                            "🛡️ NEW AEGIS SHIELD FORGED!",
                            "45m Unbroken Focus Reward",
                            f"You now hold {rpg['shields']}/3 Streak Shields!"
                        )

                save_rpg_state(rpg)
                log_result_fast(status_tag, final_score)

                new_streak = streak + 1
                if new_streak in MILESTONES:
                    play_sound("Hero")
                    send_notification(
                        "🔥 COMBO STREAK LEVEL UP!",
                        f"{new_streak} Minutes Unbroken!",
                        f"Flow Multiplier is now {min(1.0 + (min(new_streak, 60) // 15) * 0.5, 3.0)}x!"
                    )
                if in_recovery and minutes_left <= 1:
                    play_sound("Glass")
                    send_notification(
                        "✨ COGNITIVE TAX LIFTED",
                        "Attention Residue Cleared",
                        "Full XP & Loot Rolls restored!"
                    )
        except Exception:
            log_result_fast("Error", 0)

        self._refresh_menu_labels()


if __name__ == "__main__":
    app = FocusTrackerApp()
    app.run()