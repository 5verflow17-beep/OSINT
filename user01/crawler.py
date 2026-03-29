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
    """탐지된 키워드에 따라 위험도를 자동으로 계산"""
    critical_kws = ["leak", "database", "sql_dump", "credential", "root_access", "vpn_config"]
    if any(ckw in found_kws for ckw in critical_kws):
        return "CRITICAL"
    elif len(found_kws) >= 2:
        return "HIGH"
    return "MEDIUM"

def is_already_collected(cursor, url):
    """DB에서 동일한 URL이 이미 수집되었는지 확인"""
    sql = "SELECT id FROM leak_logs WHERE url = %s"
    cursor.execute(sql, (url,))
    return cursor.fetchone() is not None

# [추가] 매 스캔 완료 시 DB 전체 현황을 요약해서 보고하는 함수
def send_summary_report(new_count):
    if not WEBHOOK_URL: return
    try:
        db = pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db')
        cursor = db.cursor()
        # 위험도별 통계 조회
        cursor.execute("SELECT severity, COUNT(*) FROM leak_logs GROUP BY severity")
        rows = cursor.fetchall()
        stats = {row[0]: row[1] for row in rows}
        total_count = sum(stats.values())
        db.close()

        status_icon = "✅" if new_count == 0 else "🚨"
        color = "#36a64f" if new_count == 0 else "#eb4034"
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"{status_icon} 다크웹 모니터링 상태 보고",
                "text": (f"이번 스캔에서 *{new_count}건*의 신규 데이터가 추가되었습니다.\n\n"
                         f"*현재 DB 탐지 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건\n"
                         f"🟠 HIGH: {stats.get('HIGH', 0)}건\n"
                         f"🟡 MEDIUM: {stats.get('MEDIUM', 0)}건"),
                "footer": "OSINT System Heartbeat",
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    except Exception as e:
        print(f"⚠️ [요약 알림 에러]: {e}")

def save_to_mysql(title, url, found_kws, severity):
    try:
        db = pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db', charset='utf8mb4')
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
    if not WEBHOOK_URL: return
    color_map = {"CRITICAL": "#ff0000", "HIGH": "#ff8c00", "MEDIUM": "#ffeb3b"}
    color = color_map.get(severity, "#808080")
    payload = {
        "attachments": [{
            "color": color,
            "pretext": f"🚨 *[OSINT 관제] {severity} 등급 위협 탐지*",
            "title": f"게시물: {title}",
            "title_link": url,
            "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
            "ts": time.time()
        }]
    }
    requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})

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
                
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                
                if found:
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    if is_already_collected(cursor, full_url):
                        continue
                    
                    severity = calculate_severity(found)
                    if save_to_mysql(text, full_url, found, severity):
                        send_slack_alert(text, full_url, found, severity)
                        new_count += 1
            
            db.close()
            # [핵심] 스캔 완료 후 요약 알림 함수 호출
            send_summary_report(new_count)
            print(f"[+] 스캔 완료. 신규 데이터 {new_count}건 수집됨.")
        else:
            print(f"❌ 접속 실패: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")

if __name__ == "__main__":
    start_crawl()