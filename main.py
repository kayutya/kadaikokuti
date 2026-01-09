import os
import requests
from icalendar import Calendar
from datetime import datetime, timedelta

ICAL_URL = os.environ.get('ICAL_URL')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
CHECK_DATE = os.environ.get('CHECK_DATE')

def main():
    print(f"--- 診断開始 ---")
    print(f"入力された日付: '{CHECK_DATE}'")
    
    # 1. カレンダー取得テスト
    try:
        res = requests.get(ICAL_URL, timeout=10)
        print(f"カレンダー取得ステータス: {res.status_code}")
        cal = Calendar.from_ical(res.content)
        events = list(cal.walk('vevent'))
        print(f"取得した総イベント数: {len(events)}個")
        
        # 最初の3件だけ中身を表示してみる
        for e in events[:3]:
            print(f"  - 発見したイベント: {e.get('summary')} (締切: {e.get('dtend').dt})")
            
    except Exception as e:
        print(f"カレンダー取得エラー: {e}")

    # 2. Discord送信テスト
    test_msg = "ボットは動いているのだ！課題が見つからない原因を調査中なのだ。"
    try:
        res_disc = requests.post(WEBHOOK_URL, json={"content": test_msg})
        print(f"Discord送信ステータス: {res_disc.status_code} (204なら成功)")
    except Exception as e:
        print(f"Discord送信エラー: {e}")
    
    print(f"--- 診断終了 ---")

if __name__ == "__main__":
    main()
