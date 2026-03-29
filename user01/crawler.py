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
# [설정] 스캔 모드 및 성능 최적화 변수
# ==========================================
SCAN_MODE = "SMART"    # "SMART": 중복 시 종료 (평상시) / "FULL": 전체 스캔 (전수 조사용)
MAX_PAGES = 50        # 스캔할 최대 페이지 수
TIMEOUT_SEC = 30      # Tor 응답 대기 시간 (너무 길면 프리징처럼 보임)
# ==========================================

load_dotenv()
DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Tor 프록시 설정
PROXIES = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

# 세션 객체 생성: 매번 연결을 새로 맺지 않아 속도가 향상됨
session = requests.Session()
session.proxies = PROXIES

# 탐지 대상 키워드 (대소문자 구분 없이 매칭)
KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "삼성", "현대", "대한민국", "korea",
    "database", "leak", "sql_dump", "credential", "passport", "confidential", "internal_use"
]

def get_db_connection():
    """
    MySQL 데이터베이스 연결을 생성합니다.
    :return: pymysql connection object
    """
    return pymysql.connect(host='localhost', user='root', password=DB_PWD, db='osint_db', charset='utf8mb4')

def calculate_severity(found_kws):
    """
    탐지된 키워드 리스트를 바탕으로 위험 등급(Severity)을 계산합니다.
    :param found_kws: 발견된 키워드 리스트
    :return: "CRITICAL", "HIGH", "MEDIUM"
    """
    critical_kws = ["leak", "database", "sql_dump", "credential", "confidential"]
    if any(ckw in found_kws for ckw in critical_kws):
        return "CRITICAL"
    return "HIGH" if len(found_kws) >= 2 else "MEDIUM"

def send_slack_alert(title, url, found_kws, severity):
    """
    신규 위협 탐지 시 슬랙 채널로 실시간 알림을 보냅니다.
    """
    if not WEBHOOK_URL: return
    color_map = {"CRITICAL": "#ff0000", "HIGH": "#ff8c00", "MEDIUM": "#ffeb3b"}
    payload = {
        "attachments": [{
            "color": color_map.get(severity, "#808080"),
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
    except Exception as e:
        print(f"⚠️ 슬랙 알림 전송 실패: {e}")

def check_detail_content(url):
    """
    게시물 상세 페이지(본문)에 접속하여 키워드를 정밀 분석합니다. (네트워크 부하가 큰 작업)
    :param url: 상세 페이지 URL
    :return: 본문에서 발견된 키워드 리스트
    """
    try:
        # TIMEOUT_SEC만큼 기다려보고 응답 없으면 바로 포기 (무한 대기 방지)
        res = session.get(url, timeout=TIMEOUT_SEC)
        if res.status_code != 200: return []
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except:
        return []

def send_summary_report(new_count):
    """
    전체 스캔이 종료된 후 요약 보고서를 발송합니다.
    """
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
                "title": f"{status_icon} 다크웹 모니터링 [{SCAN_MODE}] 보고 완료",
                "text": (f"이번 스캔에서 *{new_count}건*의 신규 데이터가 추가되었습니다.\n\n"
                         f"*현재 DB 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건 | 🟠 HIGH: {stats.get('HIGH', 0)}건"),
                "ts": time.time()
            }]
        }
        requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    except:
        pass

def start_crawl():
    """
    메인 크롤링 엔진: 페이지네이션 탐색, 중복 체크, 모드별 로직 제어를 수행합니다.
    """
    print(f"[*] 최적화 스캔 시작 (모드: {SCAN_MODE}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    current_page = 1
    new_count = 0
    stop_scanning = False 
    
    db = get_db_connection()
    cursor = db.cursor()

    while not stop_scanning and current_page <= MAX_PAGES:
        page_url = f"{TARGET_URL}?page={current_page}"
        # 진행률을 시각적으로 표시하여 멈춤 현상 확인 가능하도록 함
        progress = int((current_page / MAX_PAGES) * 100)
        print(f"🔎 {current_page}페이지 탐색 시작... (전체 진행률: {progress}%)")
        
        try:
            response = session.get(page_url, timeout=TIMEOUT_SEC)
            if response.status_code != 200:
                print(f"[!] {current_page}페이지 응답 없음. 스캔을 종료합니다.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a') 
            if not links: break

            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                if not href or not text or len(text) < 5: continue
                
                full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                
                # [로그] 현재 확인 중인 게시물 출력 (프리징 확인용)
                print(f"   - 분석 중: {text[:25]}...")

                # 1. DB 중복 체크
                cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                if cursor.fetchone():
                    if SCAN_MODE == "SMART":
                        print(f"   [-] 이미 수집된 항목 발견. SMART 모드에 따라 종료.")
                        stop_scanning = True
                        break 
                    else:
                        continue # FULL 모드일 때는 다음 게시물로 진행
                
                # 2. 키워드 탐지 (제목 우선 -> 본문 나중)
                found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                
                if not found:
                    # 제목에 없으면 본문을 긁으러 감 (가장 느린 지점)
                    found = check_detail_content(full_url)
                
                # 3. 탐지 시 저장 및 알림
                if found:
                    severity = calculate_severity(found)
                    sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                             VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                    cursor.execute(sql, (text, full_url, found[0], ",".join(list(set(found))), severity, 'NEW'))
                    send_slack_alert(text, full_url, found, severity)
                    new_count += 1
                    print(f"   🔥 [탐지 성공] 위험도: {severity}")

            db.commit() # 페이지 단위로 DB 저장
            if stop_scanning: break
            current_page += 1
            time.sleep(0.5) # 서버 매너 타임

        except Exception as e:
            print(f"⚠️ {current_page}페이지 처리 중 오류 발생: {e}")
            current_page += 1

    db.close()
    send_summary_report(new_count)
    print(f"[+] 모든 스캔 프로세스가 완료되었습니다.")

if __name__ == "__main__":
    start_crawl()