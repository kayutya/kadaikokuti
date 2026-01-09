import os
import requests
from icalendar import Calendar
from datetime import datetime, date, timedelta

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def get_assignments(url):
    if not url: return {}
    try:
        response = requests.get(url)
        cal = Calendar.from_ical(response.content)
        today = (datetime.utcnow() + timedelta(hours=9)).date()
        
        daily_tasks = {} # 課題名: URL の辞書形式にする
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            end_date = end_dt.date() if isinstance(end_dt, datetime) else end_dt
            
            if end_date == today:
                summary = str(event.get('summary'))
                # カレンダーデータ内のURL（なければ空文字）を取得
                task_url = str(event.get('url')) if event.get('url') else ""
                daily_tasks[summary] = task_url
        return daily_tasks
    except:
        return {}

def main():
    tasks_1 = get_assignments(ICAL_URL_1)
    tasks_2 = get_assignments(ICAL_URL_2)
    
    # 二人のデータを合体（同じ課題名なら上書きされる）
    all_tasks = {**tasks_1, **tasks_2}

    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y/%m/%d')
    
    if all_tasks:
        message = f"📢 **{today_str} の課題締め切り通知**\n"
        for title, url in sorted(all_tasks.items()):
            if url:
                # リンクがある場合は青文字のリンクにする
                message += f"📌 [{title}]({url})\n"
            else:
                message += f"📌 {title}\n"
        message += "\n今日の課題なのだ！"
    else:
        message = f"✅ {today_str} が締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
