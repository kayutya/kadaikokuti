import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta, time
import re

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def get_assignments(url, target_dates):
    if not url: return {}
    try:
        response = requests.get(url, timeout=15)
        cal = Calendar.from_ical(response.content)
        tasks = {}
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            # 日本時間に変換
            jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
            
            # 【ロジック変更】00:00締切は「前日の24:00」として扱う
            display_dt = jst_end
            if isinstance(jst_end, datetime) and jst_end.time() == time(0, 0):
                display_dt = jst_end - timedelta(minutes=1)
            
            check_date = display_dt.date() if isinstance(display_dt, datetime) else display_dt
            
            if check_date in target_dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                uid = str(event.get('uid'))
                match = re.search(r'(\d+)', uid)
                link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                
                # 並び替え用：日付+時間（00:00をその日の最後に持ってくる場合は23:59扱いにする）
                sort_time = jst_end.strftime('%m%d%H%M')
                if jst_end.time() == time(0, 0):
                    sort_time = (jst_end - timedelta(minutes=1)).strftime('%m%d2400')
                
                label = f"[{check_date.strftime('%m/%d')}] {summary} ({time_str}締切)"
                tasks[sort_key] = {"label": label, "link": link}
        return tasks
    except: return {}

def main():
    now_jst = datetime.utcnow() + timedelta(hours=9)
    today = now_jst.date()
    
    # デフォルトのタイトルと検索範囲
    target_dates = [today]
    title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

    if CHECK_DATE and str(CHECK_DATE).strip():
        try:
            target_date = datetime.strptime(str(CHECK_DATE).strip(), '%Y-%m-%d').date()
            target_dates = [target_date]
            title = f"📅 {CHECK_DATE} の指定チェック"
        except: return
    else:
        # 金(4)・土(5)・日(6)なら、金・土・日の3日間を常にまとめて告知
        if today.weekday() in [4, 5, 6]:
            # その週の金曜日を基準にする
            friday = today - timedelta(days=(today.weekday() - 4))
            target_dates = [friday, friday + timedelta(days=1), friday + timedelta(days=2)]
            # 月曜00:00（日曜深夜）まで含めるため、月曜も判定に入れる
            target_dates.append(friday + timedelta(days=3))
            title = "📢 【週末まとめ】（金・土・日・月朝）"

    all_data = {}
    # get_assignments を改良（target_datesのみで判定）
    def get_tasks_v2(url, dates):
        if not url: return {}
        try:
            response = requests.get(url, timeout=15)
            cal = Calendar.from_ical(response.content)
            tasks = {}
            for event in cal.walk('vevent'):
                end_dt = event.get('dtend').dt
                jst_end = end_dt + timedelta(hours=9) if isinstance(end_dt, datetime) and end_dt.tzinfo else end_dt
                
                # 00:00を前日の24:00として判定
                adj_dt = jst_end - timedelta(minutes=1) if (isinstance(jst_end, datetime) and jst_end.time() == time(0,0)) else jst_end
                if adj_dt.date() in dates:
                    summary = str(event.get('summary'))
                    time_str = jst_end.strftime('%H:%M')
                    uid = str(event.get('uid'))
                    match = re.search(r'(\d+)', uid)
                    link = f"{'/'.join(url.split('/')[:3])}/mod/assign/view.php?id={match.group(1)}" if match else ""
                    sort_key = adj_dt.strftime('%m%d%H%M')
                    label = f"[{adj_dt.strftime('%m/%d')}] {summary} ({time_str}締切)"
                    tasks[sort_key] = {"label": label, "link": link}
            return tasks
        except: return {}

    all_data.update(get_tasks_v2(ICAL_URL_1, target_dates))
    all_data.update(get_tasks_v2(ICAL_URL_2, target_dates))
    
    if all_data:
        message = f"**{title}**\n\n"
        for key in sorted(all_data.keys()):
            item = all_data[key]
            message += f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
        message += "\n週末も計画的にがんばるのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はなかったのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
