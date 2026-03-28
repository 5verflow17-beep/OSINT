# Ransomware Onion Crawl Dashboard

다크웹/랜섬웨어 위협 모니터링 대시보드 프론트엔드 (React + Vite + Tailwind + Recharts)입니다.

## 🚀 빠른 시작

필수: Node.js 18+ 설치

```bash
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 로 접근

## 🧩 환경 변수

기본 API 엔드포인트는 `http://localhost:5000` 입니다.

- `VITE_API_URL`: 백엔드 API URL (예: `http://localhost:5000`)

## 📁 현재 코드 구조

```
src/
├── main.tsx            # React 렌더링 진입점
├── app/
│   └── App.tsx         # 전체 대시보드 UI, 데이터 페칭, 검색, 차트
└── styles/
    ├── index.css       # 글로벌 스타일 (Tailwind + custom)
    ├── theme.css
    └── fonts.css

python_api/
├── flask_app.py        # 선택적 백엔드 (현재 프론트엔드와 분리)
└── requirements.txt
```

## 📌 App.tsx 데이터 요구사항 및 API 엔드포인트

`App.tsx`는 다음 REST API를 호출합니다.

- `GET ${process.env.VITE_API_URL || 'http://localhost:5000'}/threats`
  - 응답: `{ status: 'ok', data: ThreatItem[] }`
  - ThreatItem: `{ id, title, source, datetime, keywords: string[] }`

- `GET /stats/summary`
  - 응답: `{ status: 'ok', data: { total: number, new_24h: number, change_percent: number } }`

- `GET /stats/daily`
  - 응답: `{ status: 'ok', data: { date: string, count: number }[] }`

- `GET /stats/hourly`
  - 응답: `{ status: 'ok', data: { hour: number, count: number }[] }`

- `GET /stats/sources`
  - 응답: `{ status: 'ok', data: { source: string, count: number }[] }`

## 💡 기능 요약

- 실시간 위협(Threat) 데이터 리스트
- 검색어 기반 필터링
- 요약 통계 카드 (총 건수, 24h 신규, 변화율)
- 일일 추세 AreaChart
- 시간대별 분포 BarChart
- 상위 소스 및 키워드 통계
- 에러/로딩 상태 처리

## 🛠️ 빌드

```bash
npm run build
```

## 🔧 추가 설정

- `/src/app/App.tsx`에서 API 응답 형식이 다르면 변환로직을 수정
- 실시간 스트리밍 필요 시 WebSocket / Server-Sent Events 추가

## 📌 참고

- 프로젝트는 `Vite` + `React 18` + `Tailwind 4` + `Recharts` 기반
- `package.json` 시작 명령: `npm run dev`
- `python_api/flask_app.py` 는 별도 서비스이고 프론트엔드와 통신하려면 API 엔드포인트를 동일하게 맞춤
