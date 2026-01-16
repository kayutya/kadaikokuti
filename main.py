import os
import requests
import logging
import re
from icalendar import Calendar
from datetime import datetime, timedelta, time, timezone
from urllib.parse import urlparse

# 設定・定数 
ICAL_URL_1 = os.environ.get('ICAL_URL')
ICAL_URL_2 = os.environ.get('ICAL_URL_2')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE_STR = os.environ.get('CHECK_DATE')

JST = timezone(timedelta(hours=9))
DISCORD_LIMIT = 2000
CHUNK_LIMIT = 1800  # 文字数が２０００だけど安パイとってる
UID_RE = re.compile(r'(\d+)')

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_base_url(url):
    """URLからスキームとドメイン(https://example.com)を抽出"""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return ""

def get_tasks_smart(url, dates):
    found_tasks = {}
    if not url:
        return {}

    base_url = get_base_url(url)
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        cal = Calendar.from_ical(response.content)
        
        for event in cal.walk('vevent'):
            end_dt = event.get('dtend').dt
            
            # タイムゾーン処理 
            if isinstance(end_dt, datetime):
                jst_end = end_dt.astimezone(JST)
            else:
                # date型（終日イベント）の場合はそのまま
                jst_end = end_dt

            # 24:00(翌日0:00)を前日分に反映させるコード
            adj_dt = jst_end
            if isinstance(jst_end, datetime) and jst_end.time() == time(0, 0):
                adj_dt = jst_end - timedelta(minutes=1)
            
            if adj_dt.date() in dates:
                summary = str(event.get('summary'))
                time_str = jst_end.strftime('%H:%M') if isinstance(jst_end, datetime) else "終日"
                
                # UIDからID抽出
                uid = str(event.get('uid'))
                match = UID_RE.search(uid)
                link = f"{base_url}/mod/assign/view.php?id={match.group(1)}" if (match and base_url) else ""
                
                task_key = f"{summary}_{time_str}"
                sort_val = adj_dt.strftime('%m%d%H%M')
                label = f"[{adj_dt.strftime('%m/%d')}] {summary} ({time_str}締切)"
                
                found_tasks[task_key] = {"sort": sort_val, "label": label, "link": link}
                
        return found_tasks

    except requests.exceptions.RequestException as e:
        logger.error(f"Fetch error ({url}): {e}")
    except Exception as e:
        logger.error(f"Parse error ({url}): {e}")
    return {}

def send_discord(content):
    if not content or not WEBHOOK_URL:
        logger.warning("Content or Webhook URL is missing.")
        return

    try:
        if len(content) <= DISCORD_LIMIT:
            requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
        else:
            # メッセージ分割して週末の課題がすごく多いときの文字数対策
            parts = content.split('\n')
            current_msg = ""
            for part in parts:
                if len(current_msg) + len(part) > CHUNK_LIMIT:
                    requests.post(WEBHOOK_URL, json={"content": current_msg}, timeout=10)
                    current_msg = "（つづき）\n"
                current_msg += part + "\n"
            if current_msg:
                requests.post(WEBHOOK_URL, json={"content": current_msg}, timeout=10)
    except Exception as e:
        logger.error(f"Discord send error: {e}")

def main():
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL is not set. Exiting.")
        return

    # UTCからJSTへ変換して７時出力の時間差ラグを解決してる
    now_jst = datetime.now(JST)
    today = now_jst.date()
    
    # 対象日付の指定してるよ~
    if CHECK_DATE_STR and CHECK_DATE_STR.strip():
        try:
            target_dates = [datetime.strptime(CHECK_DATE_STR.strip(), '%Y-%m-%d').date()]
            title = f"📅 {CHECK_DATE_STR} の指定チェック"
        except ValueError:
            logger.error(f"Invalid CHECK_DATE format: {CHECK_DATE_STR}")
            return
    else:
        # 4: Friday, 5: Saturday, 6: Sunday
        if today.weekday() in [4, 5, 6]:
            friday = today - timedelta(days=(today.weekday() - 4))
            target_dates = [friday + timedelta(days=i) for i in range(4)] # 金土日の課題
            title = "📢 【週末まとめ】（金・土・日）"
        else:
            target_dates = [today]
            title = f"📢 {today.strftime('%Y/%m/%d')} 課題告知"

    # データ取得
    data1 = get_tasks_smart(ICAL_URL_1, target_dates)
    data2 = get_tasks_smart(ICAL_URL_2, target_dates)
    
    combined = {**data1, **data2} # ここが2人のデータ結合
    
    if combined:
        message = f"**{title}**\n\n"
        # sort_valで時間列に並べてる
        sorted_keys = sorted(combined.keys(), key=lambda x: combined[x]["sort"])
        for k in sorted_keys:
            item = combined[k]
            line = f"📌 [{item['label']}]({item['link']})\n" if item['link'] else f"📌 {item['label']}\n"
            message += line
        message += "\n早めに終わらせるのだ！"
    else:
        message = f"✅ {title}\n対象期間に締め切りの課題はないのだ！"
    
    send_discord(message)

if __name__ == "__main__":
    main()
