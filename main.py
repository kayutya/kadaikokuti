import os
import requests
from icalendar import Calendar
from datetime import datetime, date, timedelta

# GitHubの「Secrets」から2人分のURLとWebhookを読み込む
ICAL_URL_1 = os.environ.get('ICAL_URL')     # あなた用
ICAL_URL_2 = os.environ.get('ICAL_URL_2')   # お友達用
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def get_assignments(url):
    if not url: return set()
    try:
        response = requests.get(url)
        cal = Calendar.from_ical(response.content)
        today = (datetime.utcnow() + timedelta(hours=9)).date()
        
        daily_tasks = set()
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            end_date = end_dt.date() if isinstance(end_dt, datetime) else end_dt
            if end_date == today:
                # 課題名をセットに追加（これで重複が防げる）
                daily_tasks.add(str(event.get('summary')))
        return daily_tasks
    except:
        return set()

def main():
    # 二人の課題を取得して合体させる（setなので重複は自動で消える）
    tasks_1 = get_assignments(ICAL_URL_1)
    tasks_2 = get_assignments(ICAL_URL_2)
    all_tasks = tasks_1 | tasks_2 

    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y/%m/%d')
    
    if all_tasks:
        message = f"📢 **{today_str} の課題締め切り通知**\n"
        for task in sorted(all_tasks):
            message += f"📌 {task}\n"
        message += "\nわすれないようにやるのだ"
    else:
        message = f"✅ {today_str} が締め切りの課題はないのだ"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
