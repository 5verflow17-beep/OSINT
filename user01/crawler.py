import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re
from dotenv import load_dotenv
from datetime import datetime

# ==========================================
# [설정] 스캔 모드 및 속도 최적화
# ==========================================
SCAN_MODE = "FULL"   # 전수 조사를 위해 일단 FULL로 설정 (완료 후 SMART로 변경)
MAX_PAGES = 50       
TIMEOUT_SEC = 30     # 90초에서 30초로 단축 (속도 향상 핵심)
# ==========================================

load_dotenv()
DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

PROXIES = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

session = requests.Session()
session.proxies = PROXIES

KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "삼성", "현대", "대한민국", "korea",
    "database", "leak", "sql_dump", "credential", "passport", "confidential", "internal_use"
]

def get_db_connection():
    return pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db', charset='utf8mb4')

def calculate_severity(found_kws):
    critical_kws = ["leak", "database", "sql_dump", "credential", "confidential"]
    if any(ckw in found_kws for ckw in critical_kws): return "CRITICAL"
    return "HIGH" if len(found_kws) >= 2 else "MEDIUM"

def send_slack_alert(title, url, found_kws, severity):
    if not WEBHOOK_URL: return
    color_map = {"CRITICAL": "#ff0000", "HIGH": "#ff8c00", "MEDIUM": "#ffeb3b"}
    payload = {
        "attachments": [{
            "color": color_map.get(severity, "#808080"),
            "pretext": f"🚨 *[OSINT 관제] {severity} 등급 신규 위협 탐지*",
            "title": f"게시물: {title}",
            "title_link": url,
            "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
            "ts": time.time()
        }]
    }
    try: requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    except: pass

def check_detail_content(url):
    """느린 본문 분석은 필요할 때만 호출"""
    try:
        res = session.get(url, timeout=TIMEOUT_SEC)
        if res.status_code != 200: return []
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except: return []

def send_summary_report(new_count):
    if not WEBHOOK_URL: return
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT severity, COUNT(*) FROM leak_logs GROUP BY severity")
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        total_count = sum(stats.values())
        db.close()

        status_icon = "✅" if new_count == 0 else "🚨"
        payload = {
            "attachments": [{
                "color": "#36a64f" if new_count == 0 else "#eb4034",
                "title": f"{status_icon} 다크웹 모니터링 [{SCAN_MODE}] 보고",
                "text": (f"이번 스캔에서 *{new_count}건*의 신규 데이터가 추가되었습니다.\n\n"
                         f"*DB 총계:* {total_count}건 | 🔴{stats.get('CRITICAL',0)} 🟠{stats.get('HIGH',0)} 🟡{stats.get('MEDIUM',0)}"),
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    except: pass

def start_crawl():
    print(f"[*] 최적화 스캔 시작 (모드: {SCAN_MODE}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    current_page = 1
    new_count = 0
    stop_scanning = False
    
    db = get_db_connection()
    cursor = db.cursor()

    while not stop_scanning and current_page <= MAX_PAGES:
        page_url = f"{TARGET_URL}?page={current_page}"
        print(f"🔎 {current_page}페이지 탐색 중... (진행률: {int((current_page/MAX_PAGES)*100)}%)")
        
        try:
            response = session.get(page_url, timeout=TIMEOUT_SEC)
            if response.status_code != 200: break

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a') 
            if not links: break

            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                if not href or not text or len(text) < 5: continue
                
                full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                
                # 중복 체크
                cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                if cursor.fetchone():
                    if SCAN_MODE == "SMART":
                        stop_scanning = True
                        break 
                    else: continue
                
                # [속도 최적화 핵심] 제목에서 먼저 검색
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                
                # 제목에 키워드가 없을 때만 '느린' 본문 분석 실행
                if not found:
                    found = check_detail_content(full_url)
                
                if found:
                    severity = calculate_severity(found)
                    sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                             VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                    cursor.execute(sql, (text, full_url, found[0], ",".join(list(set(found))), severity, 'NEW'))
                    send_slack_alert(text, full_url, found, severity)
                    new_count += 1
                    print(f"🔥 탐지: {text[:20]}...")

            db.commit()
            if stop_scanning: break
            current_page += 1
            # 대기 시간을 1.5초에서 0.5초로 단축 (서버 상태 보며 조절)
            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️ 페이지 스캔 건너뜀 (에러): {e}")
            current_page += 1 # 에러나도 다음 페이지로 진행

    db.close()
    send_summary_report(new_count)
    print(f"[+] 스캔 완료.")

if __name__ == "__main__":
    start_crawl()