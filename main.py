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
        # 日本時間の「今日」と「明日」を取得
        now = datetime.utcnow() + timedelta(hours=9)
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        daily_tasks = {}
        for event in cal.walk('vevent'):
            # 締め切り日時を取得
            end_dt = event.get('dtend').dt
            if not isinstance(end_dt, datetime):
                # 日付のみ（終日）の場合はその日を締め切りとする
                end_date = end_dt
                end_time_str = "終日"
            else:
                # 日本時間に変換して日付と時間を取得
                # iCalの時間がUTCの場合は+9時間する（LMSの仕様により調整が必要な場合あり）
                jst_end = end_dt + timedelta(hours=9) if end_dt.tzinfo else end_dt
                end_date = jst_end.date()
                end_time_str = jst_end.strftime('%H:%M')

            # 「今日」または「明日（の深夜0時付近）」を対象にする
            if end_date == today or (end_date == tomorrow and end_time_str == "00:00"):
                summary = str(event.get('summary'))
                
                # リンクの取得（url枠 または descriptionから抽出）
                task_url = str(event.get('url')) if event.get('url') else ""
                if not task_url and event.get('description'):
                    desc = str(event.get('description'))
                    if "http" in desc:
                        # 説明文の中からURLっぽいやつを探す簡易処理
                        import re
                        urls = re.findall(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', desc)
                        if urls: task_url = urls[0]
                
                # 表示用の名前（時間付き）
                display_name = f"{summary} ({end_time_str}締切)"
                daily_tasks[display_name] = task_url
        return daily_tasks
    except Exception as e:
        print(f"Error: {e}")
        return {}

def main():
    tasks_1 = get_assignments(ICAL_URL_1)
    tasks_2 = get_assignments(ICAL_URL_2)
    all_tasks = {**tasks_1, **tasks_2}

    today_str = (datetime.utcnow() + timedelta(hours=9)).strftime('%Y/%m/%d')
    
    if all_tasks:
        message = f"📢 **{today_str} 朝の課題チェック**\n"
        message += "※明日の00:00締め切り分も入ってるのだ！\n\n"
        for title, url in sorted(all_tasks.items()):
            if url:
                message += f"📌 [{title}]({url})\n"
            else:
                message += f"📌 {title}\n"
        message += "\n今日もちゃんと提出するのだ！"
    else:
        message = f"✅ 今日（および明日0時）が締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
