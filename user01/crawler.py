import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re  # 정규표현식 라이브러리 추가
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

# 키워드 리스트
KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "database", "leak", "sql_dump", "credential", "passport", "employee_list", 
    "salary", "confidential", "internal_use", "identification",
    "vpn_config", "rdp_access", "backdoor", "exploit", "root_access",
    "republic of korea", "south korea", "korea_leak"
]

# 2. MySQL 저장 함수 (detected_keywords 컬럼 반영)
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
        
        # 💡 [수정] detected_keywords 컬럼을 포함하여 INSERT
        sql = """
        INSERT INTO leak_logs (title, url, keywords, detected_keywords) 
        VALUES (%s, %s, %s, %s)
        """
        # keywords에는 첫 번째 발견 단어를, detected_keywords에는 전체 리스트를 저장
        main_keyword = found_kws[0] if found_kws else "unknown"
        all_keywords = ",".join(found_kws)
        
        cursor.execute(sql, (title, url, main_keyword, all_keywords))
        
        db.commit()
        db.close()
        print(f"💾 [DB 저장 성공] {title[:20]}... (Keywords: {all_keywords})")
    except Exception as e:
        print(f"❌ [DB 저장 실패]: {e}")

# 3. 슬랙 알림 함수
def send_slack_alert(title, url, found_kws):
    if not WEBHOOK_URL:
        print("⚠️ 슬랙 Webhook URL이 설정되지 않았습니다.")
        return

    payload = {
        "attachments": [
            {
                "fallback": "🚨 다크웹 위협 탐지 알림",
                "color": "#ff0000",
                "pretext": "🚨 *[OSINT 관제] 다크웹 정밀 위협 탐지*",
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
        print(f"[*] 다크웹 정밀 스캔 시작... (Target: {TARGET_URL})")
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
                
                # 💡 [수정] 정규표현식을 이용한 대소문자 무시 정밀 매칭
                found = []
                for kw in KEYWORDS:
                    if re.search(re.escape(kw), text, re.IGNORECASE):
                        found.append(kw)
                
                if found:
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    
                    print(f"🔥 위협 발견: {text} | 키워드: {found}")
                    save_to_mysql(text, full_url, found)
                    send_slack_alert(text, full_url, found)
            
            print("[+] 스캔 작업을 마쳤습니다.")
        else:
            print(f"❌ 접속 실패: 상태 코드 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    start_crawl()