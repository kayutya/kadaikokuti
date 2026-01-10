import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta, time
import re

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def get_assignments(url, target_dates, limit_dt_jst):
    if not url: return {}
    try:
        response = requests.get(url, timeout=15)
        cal = Calendar.from_ical(response.content)
        tasks = {}
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            check_date = jst_end.date() if isinstance(jst_end, datetime) else jst_end
            
            # 日付リストにある、または月曜朝の制限時刻より前の課題を拾う
            if check_date in target_dates or (isinstance(jst_end, datetime) and jst_end <= limit_dt_jst):
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                # 並び替え用キー：日付+時間（00:00が上に来るようにする）
                sort_key = jst_end.strftime('%m%d%H%M') if isinstance(jst_end, datetime) else check_date.strftime('%m%d9999')
                label = f"[{check_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                tasks[sort_key] = {"label": label, "link": link}
        return tasks
    except: return {}

def main():
    # 1. 今日の日本時間を取得
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    target_dates = [today]
    # デフォルトの制限（今日の終わり）
    limit_dt_jst = datetime.combine(today, time(23, 59))
    title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

    # 日付指定がある場合
    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_date = datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            limit_dt_jst = datetime.combine(target_date, time(23, 59))
            title = f"📅 {CHECK_DATE} の指定チェック"
        except: return
    else:
        # 金曜日：土日分を追加
        if today.weekday() == 4:
            target_dates += [today + timedelta(days=1), today + timedelta(days=2)]
            title = "📢 【週末まとめ】課題告知"
        # 土曜日：月曜の朝9時までを射程に入れる（ここを修正しました）
        elif today.weekday() == 5:
            target_dates += [today + timedelta(days=1)] # 日曜
            # 明後日（月曜）の朝9時をデッドラインにする
            limit_dt_jst = datetime.combine(today + timedelta(days=2), time(9, 0))
            title = "📢 【土曜/月曜朝まで】課題告知"

    all_data = {}
    all_data.update(get_assignments(ICAL_URL_1, target_dates, limit_dt_jst))
    all_data.update(get_assignments(ICAL_URL_2, target_dates, limit_dt_jst))
    
    if all_data:
        message = f"**{title}**\n\n"
        # 時間順に正しくソートして出力
        for key in sorted(all_data.keys()):
            item = all_data[key]
            message += f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
        message += "\n早めに終わらせるのが吉なのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
