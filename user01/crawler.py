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

# Tor 프록시 및 세션 설정
PROXIES = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

session = requests.Session()
session.proxies = PROXIES

# 탐지 키워드
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

def check_detail_content(url):
    """상세 페이지 깊은 분석"""
    try:
        res = session.get(url, timeout=60)
        if res.status_code != 200: return []
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except: return []

def send_summary_report(new_count, mode="전수 조사"):
    """스캔 결과 요약 보고"""
    if not WEBHOOK_URL: return
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT severity, COUNT(*) FROM leak_logs GROUP BY severity")
        stats = {row[0]: row[1] for row in cursor.fetchall()}
        total_count = sum(stats.values())
        db.close()

        payload = {
            "attachments": [{
                "color": "#4361ee",
                "title": f"📢 다크웹 {mode} 완료 보고",
                "text": (f"전체 페이지 스캔 결과 *{new_count}건*이 신규 추가되었습니다.\n\n"
                         f"*현재 DB 탐지 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건\n"
                         f"🟠 HIGH: {stats.get('HIGH', 0)}건\n"
                         f"🟡 MEDIUM: {stats.get('MEDIUM', 0)}건"),
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        print(f"📊 [{mode} 보고] 슬랙 전송 완료!")
    except: pass

def start_full_scan(max_pages=50): # 👈 최대 스캔할 페이지 수 설정
    print(f"🚀 [전수 조사 시작] 최대 {max_pages}페이지까지 모든 데이터를 긁어옵니다.")
    current_page = 1
    new_count = 0
    
    db = get_db_connection()
    cursor = db.cursor()

    while current_page <= max_pages:
        page_url = f"{TARGET_URL}?page={current_page}"
        print(f"🔎 {current_page}페이지 전수 조사 중...")
        
        try:
            response = session.get(page_url, timeout=90)
            if response.status_code != 200:
                print(f"[!] {current_page}페이지 응답 없음. 조사를 마칩니다.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a') 
            
            if not links: break

            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                if not href or not text or len(text) < 5: continue
                
                full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                
                # [변경점] 중복 체크는 하지만, 멈추지 않고 '건너뛰기(continue)'만 함
                cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                if cursor.fetchone():
                    continue # 이미 있는 건 넘어가고 다음 게시물 확인
                
                # 탐지 로직
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                if not found:
                    found = check_detail_content(full_url)
                
                if found:
                    severity = calculate_severity(found)
                    sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                             VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                    cursor.execute(sql, (text, full_url, found[0], ",".join(list(set(found))), severity, 'NEW'))
                    new_count += 1
                    print(f"🔥 신규 발견: {text[:20]}...")

            db.commit()
            current_page += 1
            time.sleep(1.5) # 전수 조사 시 서버 차단 방지를 위한 최소한의 매너 타임

        except Exception as e:
            print(f"⚠️ 에러: {e}")
            break

    db.close()
    send_summary_report(new_count, mode="전수 조사")
    print(f"[+] 전수 조사 프로세스 완료. 총 {new_count}건 추가됨.")

if __name__ == "__main__":
    start_full_scan(max_pages=50) # 👈 필요에 따라 페이지 수 조절 (보통 50~100)