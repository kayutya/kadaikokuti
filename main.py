import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import re

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def get_assignments(url, target_dates):
    if not url: return {}
    try:
        response = requests.get(url)
        cal = Calendar.from_ical(response.content)
        
        daily_tasks = {}
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            if not isinstance(end_dt, datetime):
                end_date = end_dt
                end_time_str = "終日"
            else:
                jst_end = end_dt + timedelta(hours=9) if end_dt.tzinfo else end_dt
                end_date = jst_end.date()
                end_time_str = jst_end.strftime('%H:%M')

            # ターゲットの日付リスト（今日、明日0時、または土日）に含まれているか確認
            if end_date in target_dates or (end_date == target_dates[0] + timedelta(days=1) and end_time_str == "00:00"):
                summary = str(event.get('summary'))
                task_url = ""
                
                if event.get('url'):
                    task_url = str(event.get('url'))
                elif event.get('uid'):
                    uid = str(event.get('uid'))
                    match = re.search(r'(\d+)', uid)
                    if match:
                        base_url = "/".join(url.split("/")[:3])
                        task_url = f"{base_url}/mod/assign/view.php?id={match.group(1)}"
                
                # どの日付の課題か分かるように日付も付ける
                date_label = end_date.strftime('%m/%d')
                display_name = f"[{date_label}] {summary} ({end_time_str}締切)"
                daily_tasks[display_name] = task_url
        return daily_tasks
    except:
        return {}

def main():
    now = datetime.utcnow() + timedelta(hours=9)
    today = now.date()
    
    # 検索対象の日付リストを作る
    target_dates = []
    
    if CHECK_DATE:
        try:
            target_dates = [datetime.strptime(CHECK_DATE, '%Y-%m-%d').date()]
            title_part = f"📅 {CHECK_DATE} の課題指定チェック"
        except: return
    else:
        target_dates = [today]
        title_part = f"📢 {today.strftime('%Y/%m/%d')} 朝の課題チェック"
        
        # もし今日が金曜日(4)なら、土(5)と日(6)も追加する
        if today.weekday() == 4:
            target_dates.append(today + timedelta(days=1)) # 土曜日
            target_dates.append(today + timedelta(days=2)) # 日曜日
            title_part = f"📢 【週末まとめ】{today.strftime('%m/%d')}〜 の課題告知"

    tasks_1 = get_assignments(ICAL_URL_1, target_dates)
    tasks_2 = get_assignments(ICAL_URL_2, target_dates)
    all_tasks = {**tasks_1, **tasks_2}
    
    if all_tasks:
        message = f"**{title_part}**\n"
        if today.weekday() == 4 and not CHECK_DATE:
            message += "※金曜なので土日の分もまとめて教えるのだ！\n"
        message += "\n"
        for title, url in sorted(all_tasks.items()):
            message += f"📌 [{title}]({url})\n" if url else f"📌 {title}\n"
        message += "\n週末も計画的にがんばるのだ！"
    else:
        message = f"✅ 対象期間に締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
