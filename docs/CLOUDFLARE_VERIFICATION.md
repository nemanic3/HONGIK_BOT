# 배포 검증 기록 — 2026-10-10

## 완료

- Cloudflare Pages `hongikbot`: GitHub `nemanic3/HONGIK_BOT` master 자동 배포 연결.
- `https://hongikbot.nemanic.dev`: 사용자 지정 도메인 활성, SSL 사용, 브라우저에서 실제 홈페이지 확인.
- 대체 주소: `https://hongikbot.pages.dev`.
- 설정한 Pages 변수: `NODE_VERSION=22`, `PUBLIC_APP_ORIGIN=https://hongikbot.nemanic.dev`.
- 프런트엔드 테스트 44개 통과, 정적 빌드 및 개인정보/비밀 파일 제외 검사 통과.
- Linux Django 테스트 160개 실행: 158개 통과, macOS 전용 2개 건너뜀.
- 격리된 PostgreSQL/Redis/Celery/PaddleOCR Docker 구성에서 합성 데이터 검증 통과: 회원가입, 로그인, JWT 갱신/로그아웃 폐기, 한국어 이미지와 PDF의 비동기 OCR, 소유자 미리보기, 타 계정 접근 차단, 확정, 졸업 보고서, 캐시 방지, 비공개 미디어, 프록시 인증.
- PostgreSQL 마이그레이션 및 Django 운영 보안 검사 통과.

## 운영 백엔드 대기

서버 구매 승인 전이며 실제 운영 API는 연결하지 않았다. Pages의 `API_ORIGIN`, `HONGIK_PROXY_SECRET`은 미설정으로 API는 503으로 차단된다. 서버 준비 후 Django/DB/Redis/OCR/Tunnel과 GitHub SSH secrets를 설정하고 실제 HTTPS 흐름을 다시 검증한다. 로컬 테스트는 운영 성공을 의미하지 않는다.

## 서버 비용 제안 (구매하지 않음)

Hetzner CAX21 유럽: ARM64 4 vCPU, RAM 8 GB, SSD 80 GB. Linux ARM64에서 실제 OCR를 검증했으며 Django·PostgreSQL·Redis·OCR를 한 서버에 실행한다. 유럽 위치로 한국에서 API 왕복 지연이 증가할 수 있다. 재고와 세금은 생성 시 확인한다.

| 항목 | 월 비용 (세금 별도) |
| --- | ---: |
| CAX21 | €10.49 |
| IPv4 | €0.50 |
| 서버 백업 (서버 요금의 20%) | 약 €2.10 |
| 합계 | 약 €13.09 |

2026-10-10 공식 문서 확인: [서버 요금](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), [IPv4](https://docs.hetzner.com/cloud/servers/overview/), [백업 과금](https://docs.hetzner.com/cloud/billing/faq/). Cloudflare 유료 요금제는 적용하지 않았다. 서버 백업은 암호화된 외부 백업·복원 검증을 대체하지 않는다.

## 별도 남은 작업

공개 Git 과거 이력에 남은 기존 DB/미디어 정리. 현재 커밋과 배포 산출물에서 제외했으며 로컬 원본은 보존했다. 과거 이력 재작성은 진행하지 않았다.
