[ 5verflow 팀원 계정 배정 현황 ]
User01: 김상겸 
User02: 장보근 
User03: 전혜린
User04: 신서영
User05: 박소연
User06: 배수환
User07: 최승윤

[ 서버 이용 규칙 ]
1. 개인 작업 위치: /home/ubuntu/project/members/[본인계정]/
2. 권한 관련: 패키지 설치나 서버 설정 변경은 아키텍트(User02)에게 문의
3. 주의사항: 타인의 작업 폴더 내 파일 수정 및 삭제를 엄격히 금지함.
4. 리소스 관리: 작업 종료 후에는 반드시 VS Code 연결을 끊어주세요.

[ 서버 사양 ]
- CPU: 2 vCPU / RAM: 8 GiB (m7i-flex.large)
- OS: Ubuntu 24.04 LTS

프로젝트 기본 정보
기간: 2026년 3월 (총 16일)
팀 규모: 7명
GitHub: https://github.com/5verflow17-beep/OSINT/tree/user01
주요 기능

LockBit 랜섬웨어 사이트 크롤링
키워드 기반 위협 탐지 (기업명, 국가, 유출 정보 등)
위험도별 Slack 실시간 알림 (HIGH / MEDIUM / LOW)
React 기반 통합 모니터링 대시보드 (통계, 필터링, 요약 보고서)
팀 구성 및 역할
장보근 (나) - 인프라 아키텍처 & 서버 담당

AWS EC2 Ubuntu 서버 구축 및 전체 인프라 아키텍처 설계
VSCode Remote-SSH 개발 환경 세팅 및 팀원 가이드 작성·교육
팀원별 사용자 계정 생성 및 권한 격리 (계정 충돌 방지)
Docker 컨테이너 환경 구축 및 Python 패키지 의존성 관리
MySQL DB 연동 및 네트워크 설정 지원
다른 팀원

김상경 (팀장): 전체 크롤러 개발, Slack 알림 서비스, DB 관리
최승윤: React 대시보드 구현 및 데이터 시각화
전혜린: 크롤링 대상 사이트 조사 및 다크웹 대체 사이트 탐지
박소연: 크롤링 키워드 최적화 및 위험도 분류
배수환: 프로젝트 기획 및 크롤링 사이트 조사
신서영: 프로젝트 기획 및 발표 자료 제작
기술 스택
Backend: Python, Flask, BeautifulSoup4, PyMySQL, Tor Proxy
Frontend: React, TypeScript, Recharts, Tailwind CSS
Database / Infra: MySQL, AWS EC2 (Ubuntu)
Alert: Slack

