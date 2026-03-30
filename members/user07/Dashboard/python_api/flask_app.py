import os
import subprocess
from flask import Flask, jsonify
from flask_cors import CORS
import pymysql
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '127.0.0.1'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'db': os.getenv('MYSQL_DB', 'osint_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}

app = Flask(__name__)
CORS(app)

def get_crawler_path():
    """환경에 따라 크롤러 경로 반환"""
    env = os.getenv('ENVIRONMENT', 'local')
    if env == 'server':
        return '/home/ubuntu/project/members/user01/crawler.py'
    else:
        return 'c:\\Users\\seungyun\\Desktop\\OSINT\\members\\user01\\crawler.py'

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'API is running'})

@app.route('/stats/summary', methods=['GET'])
def get_summary_stats():
    """전체 통계 요약"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # 총 위협 건수
            cursor.execute("SELECT COUNT(*) as total FROM leak_logs")
            total = cursor.fetchone()['total']
            
            # 24시간 신규 위협
            cursor.execute("SELECT COUNT(*) as new_24h FROM leak_logs WHERE detect_time >= DATE_SUB(NOW(), INTERVAL 24 HOUR)")
            new_24h = cursor.fetchone()['new_24h']
            
            # 어제와 비교한 증감률
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN DATE(detect_time) = CURDATE() THEN 1 ELSE 0 END) as today,
                    SUM(CASE WHEN DATE(detect_time) = DATE_SUB(CURDATE(), INTERVAL 1 DAY) THEN 1 ELSE 0 END) as yesterday
                FROM leak_logs
            """)
            result = cursor.fetchone()
            today_count = result['today'] or 0
            yesterday_count = result['yesterday'] or 1
            change_percent = round(((today_count - yesterday_count) / yesterday_count) * 100, 1) if yesterday_count > 0 else 0
            
        connection.close()
        return jsonify({
            'status': 'ok',
            'data': {
                'total': total,
                'new_24h': new_24h,
                'change_percent': change_percent
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stats/daily', methods=['GET'])
def get_daily_stats():
    """일일 위협 발견 트렌드 (지난 30일)"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    DATE(detect_time) as date,
                    COUNT(*) as count
                FROM leak_logs
                WHERE detect_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY DATE(detect_time)
                ORDER BY date ASC
            """)
            rows = cursor.fetchall()
        connection.close()
        
        return jsonify({
            'status': 'ok',
            'data': rows
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stats/hourly', methods=['GET'])
def get_hourly_stats():
    """시간대별 분포 (지난 7일)"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    HOUR(detect_time) as hour,
                    COUNT(*) as count
                FROM leak_logs
                WHERE detect_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY HOUR(detect_time)
                ORDER BY hour ASC
            """)
            rows = cursor.fetchall()
        connection.close()
        
        # 0~23시간을 모두 포함하도록 처리
        hourly_data = {i: 0 for i in range(24)}
        for row in rows:
            hourly_data[row['hour']] = row['count']
        
        result = [{'hour': h, 'count': hourly_data[h]} for h in range(24)]
        return jsonify({
            'status': 'ok',
            'data': result
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stats/sources', methods=['GET'])
def get_sources_stats():
    """상위 소스 분석"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN url LIKE '%lockbit%' THEN 'LockBit'
                        WHEN url LIKE '%exploit%' THEN 'Exploit.in'
                        WHEN url LIKE '%breached%' THEN 'Breached'
                        ELSE 'Other'
                    END as source,
                    COUNT(*) as count
                FROM leak_logs
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
        connection.close()
        
        return jsonify({
            'status': 'ok',
            'data': rows
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/threats', methods=['GET'])
def get_threats():
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, title, url as source, keywords, 
                DATE_FORMAT(detect_time, '%m/%d %H:%i') as datetime,
                detect_time,
                CASE 
                    WHEN keywords LIKE '%critical%' THEN 95
                    WHEN keywords LIKE '%breach%' OR keywords LIKE '%data%' THEN 85
                    WHEN keywords LIKE '%leak%' THEN 75
                    WHEN keywords LIKE '%korea%' OR keywords LIKE '%samsung%' THEN 70
                    ELSE 50
                END as risk_score
                FROM leak_logs 
                ORDER BY detect_time DESC LIMIT 100
            """)
            rows = cursor.fetchall()
        connection.close()
        
        # Parse keywords from string to array
        for row in rows:
            keywords = row.get('keywords')
            if isinstance(keywords, str) and keywords:
                row['keywords'] = [kw.strip() for kw in keywords.split(',') if kw.strip()]
            else:
                row['keywords'] = []
        
        return jsonify({'status': 'ok', 'data': rows})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/threats/<int:threat_id>', methods=['GET'])
def get_threat_detail(threat_id):
    """특정 위협 상세 정보"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, title, url as source, keywords, detect_time
                FROM leak_logs 
                WHERE id = %s
            """, (threat_id,))
            row = cursor.fetchone()
        
        if not row:
            return jsonify({'status': 'error', 'message': 'Threat not found'}), 404
        
        connection.close()
        
        # Parse keywords
        keywords_str = row.get('keywords', '')
        if isinstance(keywords_str, str) and keywords_str:
            keywords_list = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        else:
            keywords_list = []
        
        # Format datetime safely
        detect_time = row.get('detect_time')
        datetime_str = str(detect_time) if detect_time else ''
        
        result = {
            'id': row.get('id'),
            'title': row.get('title', ''),
            'source': row.get('source', ''),
            'keywords': keywords_list,
            'content': row.get('title', ''),
            'datetime': datetime_str,
            'risk_score': 75
        }
        
        return jsonify({'status': 'ok', 'data': result})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/crawler/next-run', methods=['GET'])
def get_next_crawl_time():
    """다음 크롤링 시간 정보"""
    try:
        # 실제로는 DB의 크롤러 스케줄 테이블에서 가져와야 함
        # 지금은 예시로 항상 다음 5분마다라고 반환
        from datetime import datetime as dt, timedelta
        
        # 현재 시간 기준으로 다음 5분 마크 계산 (매 정각/5분 단위)
        now = dt.now()
        minutes_to_next = 5 - (now.minute % 5)
        if minutes_to_next == 0:
            minutes_to_next = 5
        next_run = now + timedelta(minutes=minutes_to_next)
        
        return jsonify({
            'status': 'ok',
            'data': {
                'next_run': next_run.isoformat(),
                'interval_seconds': 300
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/crawl', methods=['POST'])
def run_crawl():
    try:
        crawler_path = get_crawler_path()
        result = subprocess.run(['python3', crawler_path], capture_output=True, text=True, timeout=60 * 5)

        if result.returncode != 0:
            return jsonify({'status': 'error', 'message': result.stderr or 'crawler error'}), 500

        return jsonify({'status': 'ok', 'message': 'Crawl triggered', 'output': result.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Crawler timeout'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
