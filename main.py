
import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta, time
import re

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def get_tasks_smart(url, dates):
    found_tasks = {}
    if not url: return {}
    try:
        response = requests.get(url, timeout=15)
        cal = Calendar.from_ical(response.content)
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            
            # 00:00を前日の24:00として判定
            adj_dt = jst_end - timedelta(minutes=1) if (isinstance(jst_end, datetime) and jst_end.time() == time(0,0)) else jst_end
            
            if adj_dt.date() in dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M')
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                # 「名前＋時間」で重複判定。時間が違えば別々に表示
                task_key = f"{summary}_{time_str}"
                sort_val = adj_dt.strftime('%m%d%H%M')
                label = f"[{adj_dt.strftime('%m/%d')}] {summary} ({time_str}締切)"
                found_tasks[task_key] = {"sort": sort_val, "label": label, "link": link}
        return found_tasks
    except: return {}

def send_discord(content):
    if not content: return
    # Discordの2000文字制限対策：1800文字で安全に分割
    if len(content) <= 2000:
        requests.post(WEBHOOK_URL, json={"content": content})
    else:
        parts = content.split('\n')
        current_msg = ""
        for part in parts:
            if len(current_msg) + len(part) > 1800:
                requests.post(WEBHOOK_URL, json={"content": current_msg})
                current_msg = "（つづき）\n"
            current_msg += part + "\n"
        requests.post(WEBHOOK_URL, json={"content": current_msg})

def main():
    print(f"URL1: {bool(ICAL_URL_1)}, URL2: {bool(ICAL_URL_2)}") # 2人分読み込めているかログ出力
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    if CHECK_DATE and str(CHECK_DATE).strip():
        target_dates = [datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()]
        title = f"📅 {CHECK_DATE} の指定チェック"
    else:
        # 金土日は常に週末まとめ（金〜月朝まで）
        if today.weekday() in [4, 5, 6]:
            friday = today - timedelta(days=(today.weekday() - 4))
            target_dates = [friday, friday + timedelta(days=1), friday + timedelta(days=2), friday + timedelta(days=3)]
            title = "📢 【週末まとめ】（金・土・日・月朝）"
        else:
            target_dates = [today]
            title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

    # 2人分のデータを取得して合体
    data1 = get_tasks_smart(ICAL_URL_1, target_dates)
    data2 = get_tasks_smart(ICAL_URL_2, target_dates)
    
    combined = {}
    combined.update(data1)
    combined.update(data2)
    
    if combined:
        message = f"**{title}**\n\n"
        sorted_keys = sorted(combined.keys(), key=lambda x: combined[x]["sort"])
        for k in sorted_keys:
            item = combined[k]
            line = f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
            message += line
        message += "\n早めに終わらせるのが吉なのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    send_discord(message)

if __name__ == "__main__":
    main()
