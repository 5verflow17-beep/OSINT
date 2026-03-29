import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re
from dotenv import load_dotenv

# 1. 환경 변수(.env) 로드
load_dotenv()

DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Tor 프록시 설정
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

# 정밀 탐지 키워드 리스트
KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "database", "leak", "sql_dump", "credential", "passport", "employee_list", 
    "salary", "confidential", "internal_use", "identification",
    "vpn_config", "rdp_access", "backdoor", "exploit", "root_access",
    "republic of korea", "south korea", "korea_leak"
]

# 2. 중복 확인 함수 (URL 기준)
def is_already_collected(cursor, url):
    sql = "SELECT id FROM leak_logs WHERE url = %s"
    cursor.execute(sql, (url,))
    return cursor.fetchone() is not None

# 3. MySQL 저장 함수
def save_to_mysql(title, url, found_kws):
    try:
        db = pymysql.connect(
            host='localhost',
            user='root',
            password=DB_PWD,
            db='osint_db',
            charset='utf8mb4'
        )
        cursor = db.cursor()
        
        # 정밀 탐지된 키워드들을 콤마로 합쳐서 저장
        main_keyword = found_kws[0] if found_kws else "unknown"
        all_keywords = ",".join(found_kws)
        
        sql = """
        INSERT INTO leak_logs (title, url, keywords, detected_keywords) 
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (title, url, main_keyword, all_keywords))
        
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"❌ [DB 저장 실패]: {e}")
        return False

# 4. 슬랙 알림 함수
def send_slack_alert(title, url, found_kws):
    if not WEBHOOK_URL:
        # 알림을 꺼두셨을 때 터미널에만 출력
        print(f"ℹ️ [알림 스킵] 슬랙 URL 없음: {title[:20]}...")
        return

    payload = {
        "attachments": [
            {
                "fallback": "🚨 다크웹 신규 위협 탐지",
                "color": "#ff0000",
                "pretext": "🚨 *[OSINT 관제] 신규 위협이 탐지되었습니다*",
                "title": f"게시물: {title}",
                "title_link": url,
                "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
                "footer": "DarkWeb Monitoring System",
                "ts": time.time()
            }
        ]
    }
    
    try:
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        print("🔔 [슬랙 알림] 전송 완료!")
    except Exception as e:
        print(f"⚠️ [슬랙 에러]: {e}")

# 5. 메인 크롤링 함수
def start_crawl():
    try:
        print(f"[*] 스캔 시작: {TARGET_URL}")
        response = requests.get(TARGET_URL, proxies=PROXIES, timeout=90)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            
            # DB 연결 (중복 체크용)
            db = pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db')
            cursor = db.cursor()

            new_count = 0
            for link in links:
                href = link.get('href')
                text = link.get_text().strip()
                
                if not href or not text: continue
                
                # 대소문자 무시 정밀 매칭
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                
                if found:
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    
                    # 💡 [중복 체크] 이미 DB에 있으면 저장/알림 스킵
                    if is_already_collected(cursor, full_url):
                        continue
                    
                    # 새로운 정보일 때만 실행
                    if save_to_mysql(text, full_url, found):
                        send_slack_alert(text, full_url, found)
                        new_count += 1
            
            db.close()
            print(f"[+] 스캔 완료. 신규 데이터 {new_count}건 발견.")
        else:
            print(f"❌ 접속 실패: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")

if __name__ == "__main__":
    start_crawl()