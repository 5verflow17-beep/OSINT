import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re
from dotenv import load_dotenv
from datetime import datetime

# 1. 환경 변수 로드
load_dotenv()
DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Tor 프록시 및 세션 설정 (속도 및 연결 안정성 향상)
PROXIES = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

session = requests.Session()
session.proxies = PROXIES

# 정밀 탐지 키워드
KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "삼성", "현대", "대한민국", "korea",
    "database", "leak", "sql_dump", "credential", "passport", "confidential", "internal_use"
]

def get_db_connection():
    return pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db', charset='utf8mb4')

def calculate_severity(found_kws):
    critical_kws = ["leak", "database", "sql_dump", "credential", "confidential"]
    if any(ckw in found_kws for ckw in critical_kws):
        return "CRITICAL"
    return "HIGH" if len(found_kws) >= 2 else "MEDIUM"

def send_slack_alert(title, url, found_kws, severity):
    """[복구] 신규 위협 탐지 시 실시간 개별 알림 전송"""
    if not WEBHOOK_URL: return
    color_map = {"CRITICAL": "#ff0000", "HIGH": "#ff8c00", "MEDIUM": "#ffeb3b"}
    color = color_map.get(severity, "#808080")
    
    payload = {
        "attachments": [{
            "color": color,
            "pretext": f"🚨 *[OSINT 관제] {severity} 등급 신규 위협 탐지*",
            "title": f"게시물: {title}",
            "title_link": url,
            "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
            "footer": "DarkWeb Real-time Monitor",
            "ts": time.time()
        }]
    }
    try:
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        print(f"🔔 [신규 알림] 슬랙 전송 완료! ({severity})")
    except Exception as e:
        print(f"⚠️ [알림 에러]: {e}")

def check_detail_content(url):
    """상세 페이지 본문 분석"""
    try:
        res = session.get(url, timeout=60)
        if res.status_code != 200: return []
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except:
        return []

def send_summary_report(new_count):
    """스캔 완료 후 전체 현황 보고"""
    if not WEBHOOK_URL: return
    try:
        db = get_db_connection()
        cursor = db.cursor()
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
                "title": f"{status_icon} 다크웹 모니터링 정밀 보고",
                "text": (f"이번 스마트 스캔에서 *{new_count}건*의 신규 데이터가 추가되었습니다.\n\n"
                         f"*현재 DB 탐지 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건\n"
                         f"🟠 HIGH: {stats.get('HIGH', 0)}건\n"
                         f"🟡 MEDIUM: {stats.get('MEDIUM', 0)}건"),
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        print(f"📊 [요약 보고] 슬랙 전송 완료! (신규: {new_count}건)")
    except Exception as e:
        print(f"⚠️ [요약 보고 에러]: {e}")

def start_crawl():
    print(f"[*] 스마트 정밀 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    current_page = 1
    new_count = 0
    stop_scanning = False
    
    db = get_db_connection()
    cursor = db.cursor()

    while not stop_scanning:
        page_url = f"{TARGET_URL}?page={current_page}"
        print(f"[*] {current_page}페이지 탐색 중...")
        
        try:
            response = session.get(page_url, timeout=90)
            if response.status_code != 200: break

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a') 
            
            if not links: break

            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                if not href or not text or len(text) < 5: continue
                
                full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                
                # 중복 체크 (스마트 페이지네이션 핵심)
                cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                if cursor.fetchone():
                    print(f"[-] 기수집 항목 발견. 스캔 조기 종료.")
                    stop_scanning = True
                    break 
                
                # 탐지 로직 (제목 -> 본문)
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                if not found:
                    found = check_detail_content(full_url)
                
                if found:
                    severity = calculate_severity(found)
                    main_kw = found[0]
                    all_kws = ",".join(list(set(found)))
                    
                    # 1. DB 저장
                    sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                             VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                    cursor.execute(sql, (text, full_url, main_kw, all_kws, severity, 'NEW'))
                    
                    # 2. 실시간 개별 알림 전송 (복구된 부분!)
                    send_slack_alert(text, full_url, found, severity)
                    
                    new_count += 1
                    print(f"🔥 신규 탐지: {text[:20]}...")

            db.commit()
            if stop_scanning: break
            current_page += 1
            time.sleep(1) 

        except Exception as e:
            print(f"⚠️ 에러: {e}")
            break

    db.close()
    send_summary_report(new_count)
    print(f"[+] 모든 프로세스 완료.")

if __name__ == "__main__":
    start_crawl()