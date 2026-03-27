# Ransomware Onion Crawl Dashboard

랜섬웨어 Onion 사이트(LockBit, Play, RansomHouse 등)를 실시간으로 모니터링하고 인텔리전스를 수집하는 대시보드입니다.

## 🚀 실행 방법

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

## 📁 프로젝트 구조

```
src/
├── main.tsx                    # React 애플리케이션 진입점
├── app/
│   ├── App.tsx                 # 메인 대시보드 컴포넌트
│   └── components/
│       ├── header.tsx          # 상단 헤더 (검색, 알림, 사용자 정보)
│       ├── sidebar.tsx         # 좌측 사이드바 (네비게이션)
│       ├── metric-card.tsx     # 메트릭 카드 컴포넌트
│       ├── threat-chart.tsx    # 위협 활동 차트
│       ├── threat-feed.tsx     # 실시간 위협 피드
│       ├── dark-web-monitor.tsx # 다크웹 모니터링 상태
│       └── ui/                 # 재사용 가능한 UI 컴포넌트들
└── styles/
    ├── index.css              # 메인 스타일
    ├── theme.css              # 다크 테마 설정
    └── fonts.css              # 폰트 설정
```

## 🔧 각 파일 역할 및 연동 가이드

### 1. 메인 컴포넌트들

#### `App.tsx`
**역할**: 대시보드 전체 레이아웃과 데이터 표시
**하드코딩된 부분**:
- 메트릭 카드 값들 (Active Threats, Dark Web Sources 등)
- 위협 분포 데이터 (Data Breaches, Malware 등 비율)
- 긴급 알림 데이터

**연동 시 수정사항**:
```typescript
// TODO 주석이 있는 부분들을 실제 API 데이터로 교체
const metrics = await fetch('/api/metrics').then(r => r.json());
const threatDistribution = await fetch('/api/threat-distribution').then(r => r.json());
const alerts = await fetch('/api/alerts').then(r => r.json());
```

#### `threat-chart.tsx`
**역할**: 시간별 위협 활동량을 시각화하는 차트
**하드코딩된 부분**:
- `data` 배열: 시간별 critical/high/medium 위협 수

**연동 시 수정사항**:
```typescript
// 크롤러에서 수집된 시간별 데이터를 API로 받아서 교체
const chartData = await fetch('/api/threat-activity').then(r => r.json());
```

#### `threat-feed.tsx`
**역할**: 실시간 위협 피드 표시
**하드코딩된 부분**:
- `threats` 배열: 위협 항목들 (LockBit, Play 등 사이트별)

**연동 시 수정사항**:
```typescript
// 크롤러가 감지한 실제 위협 데이터를 실시간으로 받아서 표시
const liveThreats = await fetch('/api/live-threats').then(r => r.json());
```

#### `dark-web-monitor.tsx`
**역할**: 모니터링 중인 랜섬웨어 사이트들의 상태 표시
**하드코딩된 부분**:
- `sources` 배열: LockBit, Play, RansomHouse 등의 모니터링 데이터

**연동 시 수정사항**:
```typescript
// 각 사이트별 크롤링 상태와 수집된 데이터 수를 실시간으로 업데이트
const monitoringStatus = await fetch('/api/monitoring-status').then(r => r.json());
```

### 2. UI 컴포넌트들

#### `metric-card.tsx`
**역할**: 메트릭 데이터를 카드 형태로 표시하는 재사용 컴포넌트
**수정 필요 없음**: 데이터는 상위 컴포넌트에서 props로 전달받음

#### `header.tsx`
**역할**: 검색창, 알림, 사용자 정보 표시
**연동 시 추가 가능**:
- 검색 기능: 크롤러 데이터 검색 API 연동
- 알림: 새로운 위협 감지 시 실시간 알림

#### `sidebar.tsx`
**역할**: 네비게이션 메뉴
**연동 시 추가 가능**:
- 시스템 상태 표시 (크롤러 연결 상태 등)

### 3. 스타일 파일들

#### `theme.css`
**역할**: 다크 테마 색상 변수 정의
**수정 필요 없음**: UI 색상은 그대로 유지

## 🔗 크롤러 연동 API 설계 제안

### 필수 API 엔드포인트

```typescript
// 메트릭 데이터
GET /api/metrics
// 응답: { activeThreats: number, sources: number, actors: number, iocs: number }

// 위협 활동 차트 데이터
GET /api/threat-activity
// 응답: [{ time: string, critical: number, high: number, medium: number }]

// 실시간 위협 피드
GET /api/live-threats
// 응답: [{ id: number, title: string, source: string, severity: string, time: string, type: string }]

// 사이트 모니터링 상태
GET /api/monitoring-status
// 응답: [{ name: string, count: number, status: string, change: string }]

// 위협 분포
GET /api/threat-distribution
// 응답: [{ label: string, value: number, color: string }]

// 긴급 알림
GET /api/alerts
// 응답: [{ title: string, time: string, severity: string }]
```

### 실시간 업데이트

WebSocket 또는 Server-Sent Events를 사용하여 실시간 데이터 업데이트:

```typescript
// WebSocket 연결
const ws = new WebSocket('ws://localhost:8080/ws');

// 새로운 위협 감지 시 실시간 업데이트
ws.onmessage = (event) => {
  const newThreat = JSON.parse(event.data);
  updateThreatFeed(newThreat);
};
```

## 🎯 개발 우선순위

1. **Phase 1**: 기본 크롤러 API 연동 (메트릭, 차트 데이터)
2. **Phase 2**: 실시간 피드 연동 (WebSocket)
3. **Phase 3**: 고급 기능 (필터링, 검색, 알림)

## 📝 개발 노트

- 모든 하드코딩된 데이터는 `// TODO:` 주석으로 표시되어 있음
- 크롤러 연동 시 해당 주석을 찾아서 실제 API 호출로 교체
- 현재 UI는 랜섬웨어 포커스로 이미 조정됨 (LockBit, Play, RansomHouse)
- 다크 테마와 반응형 디자인은 유지
  