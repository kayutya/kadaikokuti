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
        response = requests.get(url, timeout=10)
        cal = Calendar.from_ical(response.content)
        daily_tasks = {}
        
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            # タイムゾーン考慮（JSTに変換）
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            end_date = jst_end.date() if isinstance(jst_end, datetime) else jst_end
            end_time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"

            # 判定（指定した日付のいずれかに合致するか）
            if end_date in target_dates:
                summary = str(event.get('summary'))
                uid = str(event.get('uid'))
                # URL組み立て
                match = re.search(r'(\d+)', uid)
                task_url = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                label = f"[{end_date.strftime('%m/%d')}] {summary} ({end_time_str}締切)"
                daily_tasks[label] = task_url
        return daily_tasks
    except Exception as e:
        print(f"エラー発生: {e}")
        return {}

def main():
    now = datetime.utcnow() + timedelta(hours=9)
    today = now.date()
    
    # 日付リスト作成
    if CHECK_DATE and CHECK_DATE.strip():
        try:
            target_dates = [datetime.strptime(CHECK_DATE.strip(), '%Y-%m-%d').date()]
            title = f"📅 {CHECK_DATE} の指定チェック"
        except: return
    else:
        # 金曜なら今日・土・日の3日分を対象にする
        target_dates = [today]
        title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"
        if today.weekday() == 4:
            target_dates += [today + timedelta(days=1), today + timedelta(days=2)]
            title = "📢 【週末まとめ】課題告知"

    t1 = get_assignments(ICAL_URL_1, target_dates)
    t2 = get_assignments(ICAL_URL_2, target_dates)
    all_tasks = {**t1, **t2}
    
    if all_tasks:
        msg = f"**{title}**\n\n" + "\n".join([f"📌 [{k}]({v})" if v else f"📌 {k}" for k, v in sorted(all_tasks.items())])
        msg += "\n\n週末もがんばるのだ！"
    else:
        msg = f"✅ {today.strftime('%m/%d')} 付近に締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    main()
