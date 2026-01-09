import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import re

# Secretsから取得
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
            # 課題の締切時間を日本時間に変換
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            end_date = jst_end.date() if isinstance(jst_end, datetime) else jst_end
            
            # 探している日付リスト（今日・明日・明後日など）に含まれているか
            if end_date in target_dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                label = f"[{end_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                daily_tasks[label] = link
        return daily_tasks
    except: return {}

def main():
    # 1. 実行時の日本時間を取得
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    # 2. どの日付を検索するか決める
    target_dates = []
    
    # 手動入力がある場合
    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_date = datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            title = f"📅 {target_date.strftime('%Y-%m-%d')} の指定チェック"
        except: return
    # 入力がない場合（自動判定）
    else:
        # 基本は「今日」を入れる
        target_dates = [today]
        title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"
        
        # 今日が金曜日(4)なら、プラス3日分（土・日・月曜朝）を強制追加
        if today.weekday() == 4:
            target_dates.append(today + timedelta(days=1)) # 土曜
            target_dates.append(today + timedelta(days=2)) # 日曜
            target_dates.append(today + timedelta(days=3)) # 月曜
            title = "📢 【週末まとめ】課題告知"

    # 3. 2つのURLから課題を取得して合体
    tasks_1 = get_assignments(ICAL_URL_1, target_dates)
    tasks_2 = get_assignments(ICAL_URL_2, target_dates)
    all_tasks = {**tasks_1, **tasks_2}
    
    # 4. メッセージ作成と送信
    if all_tasks:
        message = f"**{title}**\n\n"
        for label, link in sorted(all_tasks.items()):
            message += f"📌 [{label}]({link})\n" if link else f"📌 {label}\n"
        message += "\n週末もがんばるのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
