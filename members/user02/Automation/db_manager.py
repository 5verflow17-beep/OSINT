import mysql.connector
from mysql.connector import Error

class DBManager:
    def __init__(self):
        self.config = {
            'host': '127.0.0.1',
            'user': 'root',
            'password': 'your_password', # 나중에 설정예정이용
            'database': 'osint_db',     # DB명 뭐로하지
            'port': 3306
        }

    def connect(self):
        try:
            conn = mysql.connector.connect(**self.config)
            if conn.is_connected():
                return conn
        except Error as e:
            print(f"DB 연결 실패: {e}")
            return None

    def insert_darkweb_data(self, title, content, url):
        """데이터 저장을 위한 공용 함수"""
        conn = self.connect()
        if conn:
            cursor = conn.cursor()
            query = "INSERT INTO raw_data (title, content, url, collect_at) VALUES (%s, %s, %s, NOW())"
            try:
                cursor.execute(query, (title, content, url))
                conn.commit()
                print("데이터 저장 완료!")
            except Error as e:
                print(f"쿼리 실행 실패: {e}")
            finally:
                cursor.close()
                conn.close()

# 테스트용 
if __name__ == "__main__":
    db = DBManager()
    # db.insert_darkweb_data("테스트", "내용", "http://onion...")