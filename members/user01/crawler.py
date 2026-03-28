import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
from dotenv import load_dotenv

# 1. 환경 변수(.env) 로드
load_dotenv()

# 환경 변수에서 값 가져오기 (코드 보안 유지)
DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Tor 프록시 설정
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'
KEYWORDS = ["korea", "samsung", "lg", "sk", "hyundai", "seoul"]

# 2. MySQL 저장 함수
def save_to_mysql(title, url, keywords):
    try:
        db = pymysql.connect(
            host='localhost',
            user='root',
            password=DB_PWD,
            db='osint_db',
            charset='utf8mb4'
        )
        cursor = db.cursor()
        
        # 상세 URL 컬럼 포함하여 데이터 삽입
        sql = "INSERT INTO leak_logs (title, url, keywords) VALUES (%s, %s, %s)"
        cursor.execute(sql, (title, url, ",".join(keywords)))
        
        db.commit()
        db.close()
        print(f"💾 [DB 저장 성공] {title[:20]}...")
    except Exception as e:
        print(f"❌ [DB 저장 실패]: {e}")

# 3. 슬랙 알림 함수
def send_slack_alert(title, url, found_kws):
    if not WEBHOOK_URL:
        print("⚠️ 슬랙 Webhook URL이 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    payload = {
        "attachments": [
            {
                "fallback": "🚨 다크웹 위협 탐지 알림",
                "color": "#ff0000",
                "pretext": "🚨 *[OSINT 관제] 다크웹 한국 관련 위협 탐지*",
                "title": f"탐지된 게시물: {title}",
                "title_link": url,
                "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
                "footer": "DarkWeb Monitoring System",
                "ts": time.time()
            }
        ]
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("🔔 [슬랙 알림] 전송 완료!")
    except Exception as e:
        print(f"⚠️ [슬랙 시스템 에러]: {e}")

# 4. 메인 크롤링 함수
def start_crawl():
    try:
        print(f"[*] 다크웹 스캔 시작... (Target: {TARGET_URL})")
        # Tor 네트워크를 통해 접속
        response = requests.get(TARGET_URL, proxies=PROXIES, timeout=90)
        
        if response.status_code == 200:
            print("✅ 접속 성공! 데이터를 분석합니다.")
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            
            for link in links:
                href = link.get('href')
                text = link.get_text().strip()
                
                if not href or not text:
                    continue
                
                # 키워드 매칭
                found = [kw for kw in KEYWORDS if kw in text.lower()]
                
                if found:
                    # 상대 경로를 절대 경로로 변환
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    
                    print(f"🔥 위협 발견: {text}")
                    save_to_mysql(text, full_url, found)
                    send_slack_alert(text, full_url, found)
            
            print("[+] 스캔 작업을 마쳤습니다.")
        else:
            print(f"❌ 접속 실패: 상태 코드 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    start_crawl()