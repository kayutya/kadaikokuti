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
            
            # 【判定を修正】日付リストに入っている、または制限時刻（月曜朝）より前なら採用
            is_in_dates = check_date in target_dates
            is_before_limit = isinstance(jst_end, datetime) and jst_end <= limit_dt_jst
            
            if is_in_dates or is_before_limit:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                sort_key = jst_end.strftime('%m%d%H%M') if isinstance(jst_end, datetime) else check_date.strftime('%m%d9999')
                label = f"[{check_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                tasks[sort_key] = {"label": label, "link": link}
        return tasks
    except: return {}

def main():
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    # 手動指定がある場合
    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_date = datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            limit_dt_jst = datetime.combine(target_date, time(23, 59))
            title = f"📅 {CHECK_DATE} の指定チェック"
        except: return
    # 自動判定（空欄）の場合
    else:
        # 基本は「今日」
        target_dates = [today]
        limit_dt_jst = datetime.combine(today, time(23, 59))
        title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

        # 土曜日の場合：今日(土)・明日(日)・明後日(月)の朝9時までを全部入れる
        if today.weekday() == 5:
            target_dates = [today, today + timedelta(days=1)] # 土、日
            limit_dt_jst = datetime.combine(today + timedelta(days=2), time(9, 0)) # 月曜朝9時
            title = "📢 【土曜/月曜朝まで】課題告知"
        # 金曜日の場合：今日(金)・明日(土)・明後日(日)を全部入れる
        elif today.weekday() == 4:
            target_dates = [today, today + timedelta(days=1), today + timedelta(days=2)]
            limit_dt_jst = datetime.combine(today + timedelta(days=2), time(23, 59))
            title = "📢 【週末まとめ】課題告知"

    all_data = {}
    all_data.update(get_assignments(ICAL_URL_1, target_dates, limit_dt_jst))
    all_data.update(get_assignments(ICAL_URL_2, target_dates, limit_dt_jst))
    
    if all_data:
        message = f"**{title}**\n\n"
        for key in sorted(all_data.keys()):
            item = all_data[key]
            message += f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
        message += "\n早めに終わらせるのが吉なのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
