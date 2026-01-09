import os
import requests
from icalendar import Calendar
from datetime import datetime, date, timedelta
import re

ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

def get_assignments(url):
    if not url: return {}
    try:
        response = requests.get(url)
        cal = Calendar.from_ical(response.content)
        now = datetime.utcnow() + timedelta(hours=9)
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
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

            if end_date == today or (end_date == tomorrow and end_time_str == "00:00"):
                summary = str(event.get('summary'))
                
                # --- リンク作成のロジックを強化 ---
                task_url = ""
                # 1. 直接URLがある場合
                if event.get('url'):
                    task_url = str(event.get('url'))
                
                # 2. URLがない場合、イベントID(UID)からLMSのURLを推測して組み立てる
                # Moodleの場合、UIDの数字部分が課題IDになっていることが多いです
                if not task_url and event.get('uid'):
                    uid = str(event.get('uid'))
                    # UIDから数字を抽出 (例: event123@lms.school.ac.jp -> 123)
                    match = re.search(r'(\d+)', uid)
                    if match:
                        event_id = match.group(1)
                        # LMSのベースURL（ICAL_URLのドメイン部分）を使って組み立て
                        base_url = "/".join(url.split("/")[:3])
                        task_url = f"{base_url}/mod/assign/view.php?id={event_id}"

                # 3. それでもなければ説明文から抽出
                if not task_url and event.get('description'):
                    desc = str(event.get('description'))
                    found_urls = re.findall(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', desc)
                    if found_urls: task_url = found_urls[0]
                
                display_name = f"{summary} ({end_time_str}締切)"
                daily_tasks[display_name] = task_url
        return daily_tasks
    except:
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
                # プレビューが邪魔な場合は <url> と囲むと消せますが、一旦リンクにします
                message += f"📌 [{title}]({url})\n"
            else:
                message += f"📌 {title}\n"
        message += "\n今日もちゃんと提出するのだ！"
    else:
        message = f"✅ 今日（および明日0時）が締め切りの課題はないのだ！"
    
    requests.post(WEBHOOK_URL, json={"content": message})

if __name__ == "__main__":
    main()
