import os
import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import re
from dotenv import load_dotenv
from datetime import datetime

# --- [기존 설정값 유지] ---
SCAN_MODE = "SMART"    # "SMART": 중복 시 종료 (평상시) / "FULL": 전체 스캔 (전수 조사용)
MAX_PAGES = 50        # 스캔할 최대 페이지 수
TIMEOUT_SEC = 30      # Tor 응답 대기 시간 (너무 길면 프리징처럼 보임)

# 환경 변수 로드 (.env 파일 참조)
load_dotenv()
DB_PWD = os.getenv("DB_PASSWORD")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Tor 네트워크 프록시 설정 (9050 포트)
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

# 분석 대상 다크웹 타겟 URL
TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

# HTTP 세션 및 표준 헤더 설정
session = requests.Session()
session.proxies = PROXIES
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0'
})

# 모니터링 탐지 키워드 리스트
KEYWORDS = [
    "samsung.com", "hyundai.com", "skhynix", "lgcorp", "navercorp", "kakao",
    "삼성", "현대", "대한민국", "korea",
    "database", "leak", "sql_dump", "credential", "passport", "confidential", "internal_use"
]

def get_db_connection():
    """MySQL 데이터베이스 연결 세션 생성"""
    return pymysql.connect(
        host='localhost', 
        user='root', 
        password=DB_PWD, 
        db='osint_db', 
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# --- [신규 추가: 웹 메시지 전송 버튼용 함수] ---
def send_manual_summary():
    """웹에서 버튼 클릭 시 호출: 현재 DB의 전체 통계를 요약하여 슬랙 전송"""
    print(f"[*] 사용자 요청에 의한 실시간 요약 보고서 전송 시작...")
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 실시간 DB 데이터 기반 등급별 전체 카운트 조회
            cursor.execute("SELECT severity, COUNT(*) as count FROM leak_logs GROUP BY severity")
            rows = cursor.fetchall()
            stats = {row['severity']: row['count'] for row in rows}
            total_count = sum(stats.values())
            
            # 최근 24시간 내 신규 탐지 건수 추가 조회 (보고서 퀄리티 향상)
            cursor.execute("SELECT COUNT(*) as count FROM leak_logs WHERE detect_time > NOW() - INTERVAL 1 DAY")
            new_24h = cursor.fetchone()['count']

        payload = {
            "attachments": [{
                "color": "#7B1FA2", # 보라색 (수동 보고서 전용 색상)
                "pretext": f"📊 *사용자 요청: 실시간 위협 모니터링 요약 보고*",
                "text": (f"관리자 요청에 의해 생성된 현재 시스템 리포트입니다.\n\n"
                         f"*최근 24시간 신규:* {new_24h}건\n"
                         f"*전체 DB 탐지 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건\n"
                         f"🟠 HIGH: {stats.get('HIGH', 0)}건\n"
                         f"🟡 MEDIUM: {stats.get('MEDIUM', 0)}건\n"
                         f"🟢 LOW: {stats.get('LOW', 0)}건"),
                "footer": "OSINT Manual Report System",
                "ts": int(time.time())
            }]
        }
        
        # 한글 깨짐 방지를 위해 ensure_ascii=False 및 utf-8 인코딩 적용
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            print(f"      ✅ 사용자 요청 요약 보고서 전송 완료!")
        db.close()
    except Exception as e:
        print(f"\n⚠️ 요약 보고서 전송 중 오류 발생: {e}")

def calculate_severity(found_kws):
    """탐지 키워드 조합에 따른 위험 등급 산출 로직"""
    critical_kws = ["leak", "database", "sql_dump", "credential", "confidential"]
    
    # 1순위: 유출 핵심 키워드 포함 시 CRITICAL
    if any(ckw in found_kws for ckw in critical_kws):
        return "CRITICAL"
    
    # 2순위: 키워드 개수에 따른 등급 분화
    kw_count = len(found_kws)
    if kw_count >= 3:
        return "HIGH"
    elif kw_count == 2:
        return "MEDIUM"
    else:
        return "LOW"

def send_slack_alert(title, url, found_kws, severity):
    """신규 위협 탐지 시 슬랙 개별 알림 전송 (전송 성공 시 로그 출력)"""
    if not WEBHOOK_URL:
        return

    # 위험 등급별 가시성 확보를 위한 색상 매핑
    color_map = {
        "CRITICAL": "#ff0000", # Red
        "HIGH": "#ff8c00",     # Orange
        "MEDIUM": "#ffeb3b",    # Yellow
        "LOW": "#2eb886"       # Green
    }

    payload = {
        "attachments": [{
            "color": color_map.get(severity, "#808080"),
            "pretext": f"🚨 *[{SCAN_MODE}] {severity} 등급 신규 위협 탐지*",
            "title": f"게시물: {title}",
            "title_link": url,
            "text": f"*상세 URL:* {url}\n*탐지 키워드:* `{', '.join(found_kws)}`",
            "footer": "OSINT Monitoring System",
            "ts": int(time.time())
        }]
    }

    try:
        # 한글 인코딩 수정 반영
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        # 슬랙 서버 응답 확인 후 터미널 로그 출력
        if response.status_code == 200:
            print(f"      ✅ 슬랙 메시지 전송 완료! (등급: {severity})")
    except Exception as e:
        print(f"      ⚠️ 슬랙 알림 전송 실패: {e}")

def check_detail_content(url):
    """게시물 상세 페이지 본문 데이터 정밀 스캔"""
    try:
        res = session.get(url, timeout=TIMEOUT_SEC)
        if res.status_code != 200:
            return []
            
        detail_soup = BeautifulSoup(res.text, 'html.parser')
        body_text = detail_soup.get_text().lower()
        
        return [kw for kw in KEYWORDS if kw.lower() in body_text]
    except:
        return []

def send_summary_report(new_count):
    """스캔 프로세스 종료 후 등급별 통계 요약 보고 (새로운 알림이 있을 때만 실행)"""
    # [수정] 새로운 알림이 0건이면 보고서를 보내지 않음
    if not WEBHOOK_URL or new_count == 0:
        if new_count == 0:
            print("\n[-] 새로운 탐색 결과가 없어 요약 보고서를 전송하지 않습니다.")
        return

    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 실시간 DB 데이터 기반 등급별 카운트 조회
            cursor.execute("SELECT severity, COUNT(*) as count FROM leak_logs GROUP BY severity")
            rows = cursor.fetchall()
            stats = {row['severity']: row['count'] for row in rows}
            total_count = sum(stats.values())

        payload = {
            "attachments": [{
                "color": "#36a64f",
                "pretext": f"✅ *다크웹 모니터링 [{SCAN_MODE}] 보고 완료*",
                "text": (f"이번 스캔에서 *{new_count}건*의 신규 데이터가 추가되었습니다.\n\n"
                         f"*현재 DB 탐지 총계:* {total_count}건\n"
                         f"🔴 CRITICAL: {stats.get('CRITICAL', 0)}건\n"
                         f"🟠 HIGH: {stats.get('HIGH', 0)}건\n"
                         f"🟡 MEDIUM: {stats.get('MEDIUM', 0)}건\n"
                         f"🟢 LOW: {stats.get('LOW', 0)}건"), # 등급별 통계 가시화
                "footer": "OSINT Summary Analytics",
                "ts": int(time.time())
            }]
        }
        
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
        # 요약 보고서 전송 시에도 터미널에 상태 출력
        if response.status_code == 200:
            print(f"\n      ✅ 슬랙 요약 보고서 전송 완료! (신규: {new_count}건)")
            
        db.close()
    except Exception as e:
        print(f"\n⚠️ 요약 보고서 전송 중 오류 발생: {e}")

def start_crawl():
    """메인 크롤링 엔진: 페이지 탐색 및 데이터 처리 로직"""
    # 스캔 시작 안내 로그 출력
    print(f"[*] 최적화 스캔 시작 (모드: {SCAN_MODE}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    current_page = 1
    new_count = 0
    stop_scanning = False
    
    try:
        db = get_db_connection()
        cursor = db.cursor()

        while not stop_scanning and current_page <= MAX_PAGES:
            page_url = f"{TARGET_URL}?page={current_page}"
            # 페이지 탐색 시작 로그 (진행률 삭제 반영)
            print(f"\n🔎 {current_page}페이지 탐색 시작...")
            
            try:
                response = session.get(page_url, timeout=TIMEOUT_SEC)
                if response.status_code != 200:
                    print(f"[!] {current_page}페이지 응답 없음. 스캔을 중단합니다.")
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a') 
                if not links:
                    break

                for i, link in enumerate(links):
                    text = link.get_text().strip()
                    href = link.get('href')
                    
                    if not href or not text or len(text) < 5:
                        continue
                    
                    full_url = href if href.startswith('http') else TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                    # 실시간 분석 상태 출력
                    print(f"   [{i+1}/{len(links)}] 분석 중: {text[:25]}...", end="\r")

                    # 데이터 중복 체크 및 모드별 제어
                    cursor.execute("SELECT id FROM leak_logs WHERE url = %s", (full_url,))
                    if cursor.fetchone():
                        if SCAN_MODE == "SMART":
                            # SMART 모드 시 중복 발견 즉시 종료 로그 출력
                            print(f"\n   [-] 이미 수집된 항목 발견. SMART 모드에 따라 종료.")
                            stop_scanning = True
                            break 
                        else:
                            continue
                    
                    # 1차 제목 키워드 검사 및 2차 본문 정밀 검사
                    found = [kw for kw in KEYWORDS if re.search(re.escape(kw), text, re.IGNORECASE)]
                    if not found:
                        found = check_detail_content(full_url)
                    
                    # 위협 탐지 시 DB 저장 및 알림 발송
                    if found:
                        severity = calculate_severity(found)
                        sql = """INSERT INTO leak_logs (title, url, keywords, detected_keywords, severity, status, detect_time) 
                                 VALUES (%s, %s, %s, %s, %s, %s, NOW())"""
                        cursor.execute(sql, (text, full_url, found[0], ", ".join(list(set(found))), severity, 'NEW'))
                        db.commit() 
                        
                        send_slack_alert(text, full_url, found, severity)
                        new_count += 1
                        # 탐지 성공 화력 로그 출력
                        print(f"\n      🔥 [탐지 성공] 위험도: {severity}")

                if stop_scanning:
                    break
                    
                current_page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"\n⚠️ {current_page}페이지 처리 중 오류 발생: {e}")
                current_page += 1

        db.close()
        # 최종 요약 보고서 발송 (새로운 알림이 있을 때만 동작하도록 내부 로직 반영됨)
        send_summary_report(new_count)
        print(f"\n[+] 모든 스캔 프로세스가 완료되었습니다.")

    except Exception as e:
        print(f"[!] 시스템 치명적 오류: {e}")

if __name__ == "__main__":
    # 스크립트 실행 진입점
    # 1. 일반 크롤링 실행 시: start_crawl()
    # 2. 웹에서 버튼 눌러 보고서만 보낼 시: send_manual_summary() 호출 필요
    start_crawl()