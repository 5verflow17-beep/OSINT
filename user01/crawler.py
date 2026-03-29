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

# Tor 프록시 및 타겟 설정
PROXIES = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

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

def check_detail_content(url):
    """상세 페이지 본문에서 키워드 재검색 (누락 방지)"""
    try:
        res = requests.get(url, proxies=PROXIES, timeout=60)
        if res.status_code != 200: return []
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except:
        return []

def send_summary_report(new_count):
    """스캔 결과 요약 보고 (신규 데이터 유무와 상관없이 전송)"""
    if not WEBHOOK_URL: return
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT severity, COUNT(*) FROM leak_logs GROUP BY severity")
        stats = {row[0]: row[1] for row in cursor.fetchall()}
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
                "footer": "OSINT Deep Scan System",
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        print(f"📊 [슬랙 요약 보고] 전송 완료! (신규: {new_count}건 / 전체: {total_count}건)")
    except Exception as e:
        print(f"⚠️ [요약 알림 에러]: {e}")

def start_crawl():
    print(f"[*] 스마트 정밀 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    current_page = 1
    new_count = 0
    stop_scanning = False # 중복 발견 시 스캔을 멈추기 위한 플래그
    
    db = get_db_connection()
    cursor = db.cursor()

    while not stop_scanning:
        # 페이지별 URL 생성 (사이트 구조에 따라 ?page= 혹은 /page/ 등으로 수정 필요)
        page_url = f"{TARGET_URL}?page={current_page}"
        print(f"[*] {current_page}페이지 탐색 중...")
        
        try:
            response = requests.get(page_url, proxies=PROXIES, timeout=90)
            if response.status_code != 200:
                print("[!] 더 이상 페이지가 없거나 서버 응답이 없습니다.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a') # 실제 타겟의 게시글 링크 패턴에 맞게 조정 필요
            
            if not links:
                break

            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                if not href or not text or len(text) < 5: continue
                
                full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                
                # [스마트 체크] 이미 DB에 있는 URL을 만나면 과거 데이터로 간주하고 전체 스캔 중지
                cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                if cursor.fetchone():
                    print(f"[-] 이미 수집된 항목 발견 ({text[:15]}...). 스캔을 종료합니다.")
                    stop_scanning = True
                    break 
                
                # 1단계: 제목 검색 -> 2단계: 본문 검색 (누락 방지)
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                if not found:
                    found = check_detail_content(full_url)
                
                if found:
                    severity = calculate_severity(found)
                    sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                             VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                    cursor.execute(sql, (text, full_url, found[0], ",".join(list(set(found))), severity, 'NEW'))
                    new_count += 1
                    print(f"🔥 신규 탐지: {text[:20]}... ({severity})")

            db.commit()
            if stop_scanning: break
            
            current_page += 1
            time.sleep(2) # 다크웹 서버 부하 방지를 위한 매너 타임

        except Exception as e:
            print(f"⚠️ {current_page}페이지 처리 중 에러: {e}")
            break

    db.close()
    send_summary_report(new_count)
    print(f"[+] 스캔 프로세스 완료.")

if __name__ == "__main__":
    start_crawl()