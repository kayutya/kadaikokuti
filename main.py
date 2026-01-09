import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import re

# 1. 2つのURLとWebhookを確実に取得
ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
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
            # 日本時間に変換して判定
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            end_date = jst_end.date() if isinstance(jst_end, datetime) else jst_end
            
            # 指定された日付リストに含まれているか
            if end_date in target_dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                # LMSのURLを動的に生成
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                label = f"[{end_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                daily_tasks[label] = link
        return daily_tasks
    except: return {}

def main():
    # 2. 日本時間を基準にする
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    # 3. 検索対象の日付を決定
    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_date = datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            title = f"📅 {target_date.strftime('%Y-%m-%d')} の指定チェック"
        except: return
    else:
        # 空欄（自動）なら「今日」
        target_dates = [today]
        title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"
        # 金曜（4）なら日曜（+2）までを確実に入れる
        if today.weekday() == 4:
            target_dates += [today + timedelta(days=1), today + timedelta(days=2)]
            title = "📢 【週末まとめ】課題告知"

    # 4. ★ここが重要！2つのURLから順番に取得して「1つのリスト」に合体
    all_tasks = {}
    
    # 1人目の課題を取得
    tasks_1 = get_assignments(ICAL_URL_1, target_dates)
    all_tasks.update(tasks_1)
    
    # 2人目（お友達）の課題を取得
    tasks_2 = get_assignments(ICAL_URL_2, target_dates)
    all_tasks.update(tasks_2)
    
    # 5. 結果を送信
    if all_tasks:
        message = f"**{title}**\n\n"
        # 締切日順（labelの先頭の[01/09]など）で並び替え
        for label in sorted(all_tasks.keys()):
            link = all_tasks[label]
            message += f"📌 [{label}]({link})\n" if link else f"📌 {label}\n"
        message += "\n週末もがんばるのだ！"
    else:
        # 動いていることを確認するために、0件でも通知
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
