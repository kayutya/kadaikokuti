import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import re

ICAL_URL = os.environ.get('ICAL_URL')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def get_assignments(url, target_dates):
    if not url: return {}
    try:
        response = requests.get(url, timeout=15)
        cal = Calendar.from_ical(response.content)
        daily_tasks = {}
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            # 日本時間(UTC+9)へ変換
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            end_date = jst_end.date() if isinstance(jst_end, datetime) else jst_end
            
            if end_date in target_dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                
                # Moodleの課題ページURLを推測
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                label = f"[{end_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                daily_tasks[label] = link
        return daily_tasks
    except: return {}

def main():
    now = datetime.utcnow() + timedelta(hours=9)
    today = now.date()
    
    # 日付指定がある場合
    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_dates = [datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()]
            title = f"📅 {CHECK_DATE} の課題"
        except: return
    # 通常（金曜は週末分も）
    else:
        target_dates = [today]
        if today.weekday() == 4: # 金曜日
            target_dates += [today + timedelta(days=1), today + timedelta(days=2)]
            title = "📢 【週末まとめ】課題告知"
        else:
            title = f"📢 {today.strftime('%m/%d')} の課題"

    all_tasks = get_assignments(ICAL_URL, target_dates)
    
    if all_tasks:
        message = f"**{title}**\n\n"
        for label, link in sorted(all_tasks.items()):
            message += f"📌 [{label}]({link})\n" if link else f"📌 {label}\n"
        message += "\n週末もがんばるのだ！"
    else:
        # 届かない不安をなくすため、課題ゼロでも通知する
        message = f"✅ {title}：対象期間に締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
