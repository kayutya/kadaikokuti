import os
import requests
import logging
import re
from icalendar import Calendar
from datetime import datetime, timedelta, time, timezone
from urllib.parse import urlparse

# 設定・定数
ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE_STR = os.environ.get('CHECK_DATE')

JST = timezone(timedelta(hours=9))
DISCORD_LIMIT = 2000
CHUNK_LIMIT = 1800 # 文字数制限対策の安全マージン
UID_RE = re.compile(r'(\d+)')

# 早朝の定義（1:00〜9:00）
MORNING_START = 1
MORNING_END = 9

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_base_url(url):
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""

def classify_task_time(jst_end):
    if isinstance(jst_end, datetime):
        h = jst_end.hour
        if MORNING_START <= h < MORNING_END:
            return True
    return False

def get_tasks_smart(url, dates):
    found_tasks = {}
    if not url: return {}
    base_url = get_base_url(url)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        cal = Calendar.from_ical(response.content)
        for event in cal.walk('vevent'):
            try:
                end_dt = event.get('dtend').dt
                if isinstance(end_dt, datetime):
                    jst_end = end_dt.astimezone(JST)
                else:
                    jst_end = end_dt
                
                # 00:00 は前日の24:00扱い
                adj_dt = jst_end
                if isinstance(jst_end, datetime) and jst_end.time() == time(0, 0):
                    adj_dt = jst_end - timedelta(minutes=1)

                if adj_dt.date() in dates:
                    summary = str(event.get('summary'))
                    time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                    uid = str(event.get('uid'))
                    match = UID_RE.search(uid)
                    link = f"{base_url}/mod/assign/view.php?id={match.group(1)}" if (match and base_url) else ""
                    
                    is_morning = classify_task_time(jst_end)
                    note = f" ※早朝締切の課題なのだ（{MORNING_START:02d}:01〜{MORNING_END:02d}:00）" if is_morning else ""
                    
                    task_key = f"{summary}_{time_str}"
                    sort_val = adj_dt.strftime('%m%d%H%M')
                    label = f"[{adj_dt.strftime('%m/%d')}] {summary} ({time_str}締切){note}"
                    
                    found_tasks[task_key] = {
                        "sort": sort_val, "label": label, "link": link, 
                        "adj_dt": adj_dt, "is_morning": is_morning
                    }
            except Exception as e:
                continue
        return found_tasks
    except Exception as e:
        return {}

def send_discord(content):
    if not content or not WEBHOOK_URL: return
    try:
        if len(content) <= DISCORD_LIMIT:
            requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
        else:
            parts = content.split('\n')
            current_msg = ""
            for part in parts:
                if len(current_msg) + len(part) > CHUNK_LIMIT:
                    requests.post(WEBHOOK_URL, json={"content": current_msg}, timeout=10)
                    current_msg = "（つづき）\n"
                current_msg += part + "\n"
            if current_msg:
                requests.post(WEBHOOK_URL, json={"content": current_msg}, timeout=10)
    except Exception as e:
        logger.error(f"Discord send error: {e}")

def main():
    if not WEBHOOK_URL: return
    now_jst = datetime.now(JST)
    today = now_jst.date()

    if CHECK_DATE_STR and CHECK_DATE_STR.strip():
        try:
            target_date = datetime.strptime(CHECK_DATE_STR.strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            title = f"📅 {CHECK_DATE_STR} の指定チェック"
        except ValueError: return
    else:
        # 金土日は「今日〜月曜朝」まで、平日は「今日〜明日早朝」まで
        if today.weekday() in [4, 5, 6]:
            target_dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
            title = f"📢 {today.strftime('%Y/%m/%d')} 週末まとめ告知"
        else:
            target_dates = [today, today + timedelta(days=1)]
            title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

    data1 = get_tasks_smart(ICAL_URL_1, target_dates)
    data2 = get_tasks_smart(ICAL_URL_2, target_dates)
    combined = {**data1, **data2}

    filtered = {}
    for k, v in combined.items():
        task_date = v["adj_dt"].date()
        if CHECK_DATE_STR and CHECK_DATE_STR.strip():
            filtered[k] = v
            continue
        
        # 週末モード
        if today.weekday() in [4, 5, 6]:
            if task_date in target_dates: filtered[k] = v
        # 平日モード
        else:
            if task_date == today: filtered[k] = v
            elif task_date == (today + timedelta(days=1)) and v["is_morning"]: filtered[k] = v

    if filtered:
        message = f"**{title}**\n\n"
        sorted_keys = sorted(filtered.keys(), key=lambda x: filtered[x]["sort"])
        for k in sorted_keys:
            item = filtered[k]
            message += f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
        message += "\n早めに終わらせるのだ！ ういはvEを早く買うのだ"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はないのだ！"
    
    send_discord(message)

if __name__ == "__main__":
    main()
