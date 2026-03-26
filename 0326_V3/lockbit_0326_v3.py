"""
LockBit 다크웹 모니터링 시스템
- Tor 프록시 크롤링
- 한국 관련 키워드 탐지
- MySQL 저장 + 중복 방지
- 로그 파일 기록

250326_ v3
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# DB 모듈
from database import Database

# ============================================
# 환경 설정
# ============================================
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('darkweb_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 환경 변수
DB_PWD = os.getenv("DB_PASSWORD")

if not DB_PWD:
    logger.error(" .env 파일에 DB_PASSWORD가 설정되지 않았습니다!")
    sys.exit(1)

# Tor 프록시
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

TARGET_URL = 'http://lockbit3753ekiocyo5epmpy6klmejchjtzddoekjlnt6mu3qh4de2id.onion/'

# ============================================
# 키워드 설정
# ============================================
KEYWORDS = {
    "primary": [  # 확실한 한국
        ".co.kr", ".go.kr", ".or.kr", ".ac.kr",
        "seoul", "busan", "incheon", "서울", "부산",
        "south korea", "republic of korea",
        "대한민국", "한국"
    ],
    "secondary": [  # 추가 검증 필요
        "korea", "korean"
    ],
    "companies": [  # 주요 기업
        "samsung", "삼성", "lg", "sk", "hyundai", "현대",
        "kia", "기아", "posco", "포스코", "hanwha", "한화",
        "lotte", "롯데", "gs", "kt", "skt"
    ]

}

# ============================================
# 키워드 매칭
# ============================================
def check_keywords(text):
    """
    텍스트에서 한국 관련 키워드 탐지
    Returns: (is_match, matched_keywords, is_critical)
    """
    text_lower = text.lower()
    
    # 제외 키워드 체크
    if any(ex in text_lower for ex in KEYWORDS['exclude']):
        return False, [], False
    
    matched = []
    
    # 1차 키워드
    for kw in KEYWORDS['primary']:
        if kw.lower() in text_lower:
            matched.append(kw)
    
    # 주요 기업 (Critical)
    critical_match = []
    for kw in KEYWORDS['companies']:
        if kw.lower() in text_lower:
            matched.append(kw)
            critical_match.append(kw)
    
    # 2차 키워드
    if not matched:
        for kw in KEYWORDS['secondary']:
            if kw.lower() in text_lower:
                matched.append(kw)
    
    is_critical = len(critical_match) > 0
    return len(matched) > 0, matched, is_critical

# ============================================
# 메인 크롤링
# ============================================
def start_crawl():
    """다크웹 크롤링 + 분석 + DB 저장"""
    
    logger.info("="*60)
    logger.info(f" 다크웹 스캔 시작")
    logger.info(f" Target: {TARGET_URL}")
    logger.info("="*60)
    
    # DB 초기화
    db = Database(DB_PWD)
    
    try:
        # Tor 연결
        logger.info(" Tor 네트워크 연결 중...")
        response = requests.get(
            TARGET_URL, 
            proxies=PROXIES, 
            timeout=120,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        if response.status_code != 200:
            logger.error(f" 접속 실패: HTTP {response.status_code}")
            return
        
        logger.info(" 다크웹 접속 성공! 데이터 분석 중...")
        
        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        logger.info(f" 총 {len(links)}개 링크 발견")
        
        new_count = 0
        korea_count = 0
        critical_count = 0
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if not text or len(text) < 3:
                continue
            
            # 키워드 매칭
            is_match, keywords, is_critical = check_keywords(text)
            
            if is_match:
                # URL 정규화
                if not href.startswith('http'):
                    full_url = TARGET_URL.rstrip('/') + '/' + href.lstrip('/')
                else:
                    full_url = href
                
                # 로그 출력
                emoji = "" if is_critical else ""
                logger.warning(f"{emoji} [한국 관련 탐지] {text[:50]}...")
                logger.info(f"   키워드: {', '.join(keywords[:5])}")
                
                korea_count += 1
                if is_critical:
                    critical_count += 1
                
                # DB 저장 (중복 체크)
                is_new = db.save_leak(text, full_url, keywords)
                
                if is_new:
                    new_count += 1
        
        # 통계
        stats = db.get_stats()
        logger.info("="*60)
        logger.info(f" 스캔 완료")
        logger.info(f"   🇰🇷 한국 관련 탐지: {korea_count}건")
        logger.info(f"    주요 기업: {critical_count}건")
        logger.info(f"    신규 저장: {new_count}건")
        logger.info(f"    전체 누적: {stats['total']}건")
        logger.info(f"    오늘 탐지: {stats['today']}건")
        logger.info("="*60)
        
    except requests.exceptions.RequestException as e:
        logger.error(f" [네트워크 에러] {e}")
        
    except Exception as e:
        logger.error(f" [예기치 않은 에러] {e}", exc_info=True)
        
    finally:
        db.close()

# ============================================
# 실행
# ============================================
if __name__ == "__main__":
    try:
        start_crawl()
    except KeyboardInterrupt:
        logger.info("\n 사용자에 의해 중단됨")
    except Exception as e:
        logger.critical(f" 치명적 에러: {e}", exc_info=True)