import os
import requests
from icalendar import Calendar
from datetime import datetime, date, timedelta

# GitHubの「Secrets」からURLを読み込む設定
ICAL_URL = os.environ.get('ICAL_URL')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def check_assignments():
    response = requests.get(ICAL_URL)
    cal = Calendar.from_ical(response.content)
    
    # 実行時の日付（日本時間）を取得
    # GitHub Actionsは標準時で動くため、日付判定を調整
    today = (datetime.utcnow() + timedelta(hours=9)).date()
    assignments = []

    for event in cal.walk('vevent'):
        # 締め切り時間を取得
        end_dt = event.get('dtend').dt
        if isinstance(end_dt, datetime):
            end_date = end_dt.date()
        else:
            end_date = end_dt
        
        # 今日が締め切りのものを探す
        if end_date == today:
            summary = event.get('summary')
            assignments.append(f"📌 **{summary}**")

    if assignments:
        message = f"【朝の課題通知】\n今日（{today}）が締め切りの課題なのだ\n" + "\n".join(assignments)
    else:
        message = f"✅ 今日（{today}）が締め切りの課題はないのだ"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    check_assignments()
