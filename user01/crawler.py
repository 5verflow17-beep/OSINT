import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re
from dotenv import load_dotenv
from datetime import datetime

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

def calculate_severity(found_kws):
    """탐지된 키워드에 따라 위험도를 자동으로 계산 (서비스용 로직)"""
    critical_kws = ["leak", "database", "sql_dump", "credential", "root_access", "vpn_config"]
    # 발견된 키워드 중 크리티컬한 것이 있으면 CRITICAL, 아니면 개수에 따라 차등
    if any(ckw in found_kws for ckw in critical_kws):
        return "CRITICAL"
    elif len(found_kws) >= 2:
        return "HIGH"
    return "MEDIUM"

def is_already_collected(cursor, url):
    """DB에서 동일한 URL이 이미 수집되었는지 확인 (중복 방지)"""
    sql = "SELECT id FROM leak_logs WHERE url = %s"
    cursor.execute(sql, (url,))
    return cursor.fetchone() is not None

def save_to_mysql(title, url, found_kws, severity):
    """신규 컬럼(severity, status)을 포함하여 데이터 저장"""
    try:
        db = pymysql.connect(
            host='localhost',
            user='root',
            password=DB_PWD,
            db='osint_db',
            charset='utf8mb4'
        )
        cursor = db.cursor()
        
        main_keyword = found_kws[0] if found_kws else "unknown"
        all_keywords = ",".join(found_kws)
        
        sql = """
        INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(sql, (title, url, main_keyword, all_keywords, severity, 'NEW'))
        
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"❌ [DB 저장 실패]: {e}")
        return False

def send_slack_alert(title, url, found_kws, severity):
    """위험도(Severity)에 따라 색상이 변하는 슬랙 알림"""
    if not WEBHOOK_URL: return

    # 위험도별 색상 설정
    color_map = {"CRITICAL": "#ff0000", "HIGH": "#ff8c00", "MEDIUM": "#ffeb3b"}
    color = color_map.get(severity, "#808080")

    payload = {
        "attachments": [
            {
                "fallback": f"🚨 [{severity}] 위협 탐지",
                "color": color,
                "pretext": f"🚨 *[OSINT 관제] {severity} 등급 위협 탐지*",
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
        print(f"🔔 [슬랙 알림] 전송 완료! ({severity})")
    except Exception as e:
        print(f"⚠️ [슬랙 에러]: {e}")

def start_crawl():
    try:
        print(f"[*] 스캔 시작: {TARGET_URL} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        response = requests.get(TARGET_URL, proxies=PROXIES, timeout=90)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            
            db = pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db')
            cursor = db.cursor()

            new_count = 0
            for link in links:
                href = link.get('href')
                text = link.get_text().strip()
                if not href or not text: continue
                
                # 정규표현식 정밀 탐지
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                
                if found:
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    
                    # 💡 [핵심] 중복 체크: 이미 있으면 다음 루프로 점프
                    if is_already_collected(cursor, full_url):
                        continue
                    
                    # 위험도 계산
                    severity = calculate_severity(found)
                    
                    # 신규 데이터 저장 및 알림
                    if save_to_mysql(text, full_url, found, severity):
                        send_slack_alert(text, full_url, found, severity)
                        new_count += 1
                        print(f"🔥 신규 탐지 [{severity}]: {text[:20]}...")
            
            db.close()
            print(f"[+] 스캔 완료. 신규 데이터 {new_count}건 수집됨.")
        else:
            print(f"❌ 접속 실패: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")

if __name__ == "__main__":
    start_crawl()