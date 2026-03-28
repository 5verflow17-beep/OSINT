"""
MySQL 데이터베이스 관리 모듈
"""

import pymysql
from pymysql.err import IntegrityError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, password):
        self.conn = None
        self.password = password
        self.connect()
    
    def connect(self):
        """DB 연결"""
        for attempt in range(3):
            try:
                self.conn = pymysql.connect(
                    host='localhost',
                    user='root',
                    password=self.password,
                    db='osint_db',
                    charset='utf8mb4',
                    autocommit=False
                )
                logger.info(" MySQL 연결 성공")
                return
            except Exception as e:
                logger.warning(f" DB 연결 시도 {attempt+1}/3 실패: {e}")
                if attempt < 2:
                    import time
                    time.sleep(2)
        
        logger.error(" DB 연결 실패!")
        raise Exception("Database connection failed")
    
    def save_leak(self, title, url, keywords):
        """
        유출 정보 저장 (중복 방지)
        Returns: True(신규), False(중복)
        """
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            sql = """
                INSERT INTO leak_logs (title, url, keywords, detected_at) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (
                title, 
                url, 
                ",".join(keywords),
                datetime.now()
            ))
            
            self.conn.commit()
            logger.info(f" [DB 저장] {title[:30]}...")
            return True
            
        except IntegrityError:
            self.conn.rollback()
            logger.debug(f" [중복] {title[:30]}...")
            return False
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f" [DB 에러] {e}")
            return False
            
        finally:
            if cursor:
                cursor.close()
    
    def get_stats(self):
        """통계 조회"""
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN DATE(detected_at) = CURDATE() THEN 1 END) as today
                FROM leak_logs
            """)
            result = cursor.fetchone()
            cursor.close()
            return result
        except Exception as e:
            logger.error(f" [통계 조회 실패] {e}")
            return {"total": 0, "today": 0}
    
    def close(self):
        if self.conn:
            self.conn.close()
            logger.info(" DB 연결 종료")