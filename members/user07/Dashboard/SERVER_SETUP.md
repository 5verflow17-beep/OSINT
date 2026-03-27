# 다크웹 위협 모니터링 대시보드

간소화된 다크웹 위협 모니터링 대시보드입니다.

## 환경 설정

### 로컬 테스트 (Windows)

1. **Flask API 서버 시작**
```bash
cd python_api
pip install -r requirements.txt
python flask_app.py
```

2. **Vite 개발 서버 시작**
```bash
npm install
npm run dev
```

3. **.env 확인**
```
VITE_API_URL=http://localhost:5000
ENVIRONMENT=local
```

### 서버 배포 (Ubuntu 15.135.217.68)

1. **서버에 파일 전송**
```bash
scp -r -i 5verflow-key.pem . ubuntu@15.135.217.68:/home/ubuntu/project/dashboard
```

2. **서버에서 Flask API 설정**
```bash
cd /home/ubuntu/project/dashboard/python_api
pip install -r requirements.txt
# .env 파일 수정: ENVIRONMENT=server, MYSQL_HOST=127.0.0.1
python flask_app.py
```

3. **React 빌드 및 배포**
```bash
npm install
npm run build
# 빌드된 dist/ 폴더를 웹 서버로 배포
```

4. **.env 설정 (서버용)**
```
VITE_API_URL=http://15.135.217.68:5000
ENVIRONMENT=server
MYSQL_HOST=127.0.0.1
MYSQL_USER=ubuntu
MYSQL_DB=osint_db
```

## 디렉토리 구조

```
/
├── src/
│   ├── app/
│   │   ├── App.tsx (메인 대시보드 컴포넌트)
│   │   └── components/
│   │       └── ui/ (Shadcn UI 컴포넌트)
│   └── main.tsx
├── python_api/
│   ├── flask_app.py (Flask API 서버)
│   └── requirements.txt
├── .env (환경 변수)
└── vite.config.ts
```

## API 엔드포인트

- `GET /health` - API 상태 확인
- `GET /threats` - 위협 목록 조회
- `POST /crawl` - 크롤러 실행

## 주요 기능

- 🔍 **검색**: 키워드로 위협 검색
- 📊 **통계**: 키워드별 통계 표시
- 📰 **위협 목록**: 최근 확인된 위협 표시

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| VITE_API_URL | API 서버 주소 | http://localhost:5000 |
| MYSQL_HOST | MySQL 호스트 | 127.0.0.1 |
| MYSQL_PORT | MySQL 포트 | 3306 |
| MYSQL_USER | MySQL 사용자 | root |
| MYSQL_PASSWORD | MySQL 비밀번호 | 1234 |
| MYSQL_DB | 데이터베이스 | osint_db |
| ENVIRONMENT | 환경 (local/server) | local |
