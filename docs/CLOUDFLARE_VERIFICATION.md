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

## Mac mini 운영 백엔드

사용자가 유료 서버를 거절하고 기존 Mac mini 사용을 선택했다. 새 운영 PostgreSQL/Redis/Django/Celery를 Docker로 실행하고 전용 Cloudflare Tunnel `hongikbot-macmini`를 생성했다. `hongikbot-origin.nemanic.dev`는 `http://api:8000`에만 연결된다. 운영 Pages에 `API_ORIGIN=https://hongikbot-origin.nemanic.dev`와 암호화 `HONGIK_PROXY_SECRET`을 설정했다. 실제 사용자 도메인에서 가상 계정 회원가입과 로그인 성공을 확인했다.

Mac 전용 운영 체크아웃은 `~/Library/Application Support/HongikBot/repository`에 있다. 개발 데이터는 복사하지 않았다. LaunchAgent `dev.nemanic.hongikbot`가 5분마다 GitHub master push 검증 성공 커밋을 자동 배포한다. 첫 자동 배포 `c07113d`의 마이그레이션, 운영 보안 검사, 모델 준비, 컨테이너 정상 상태를 확인했다. SSH 배포 workflow는 비활성으로 유지한다.

운영 컨테이너 내부에서도 별도의 합성 계정 두 개로 이미지/PDF 비동기 OCR, 원본 미리보기, 타 계정 접근 거부, 확정, 보고서, 토큰 갱신/폐기, private/no-store, 미디어 차단, 프록시 인증 검증을 모두 통과했다. 명령행 HTTPS 요청은 Cloudflare 오류 1010으로 차단되며 보안 설정을 낮추지 않았다.

사용자가 Chrome 파일 접근을 허용한 뒤 공개 HTTPS 브라우저 검증을 완료했다: 가짜 한국어 PNG와 텍스트 PDF 동시 업로드, 비동기 OCR done, PDF 원본 미리보기, OCR 성적 AO를 A0로 수정, 인정 선택, 확정 저장, 대시보드에 가상과목 3학점/A0 및 졸업 보고서 표시, 로그아웃. 모든 검증 계정과 업로드 원본은 종료 후 정리했다. 실제 성적표 및 개인정보를 테스트에 사용하지 않았다. 기존 제공 기준은 초안/출처 미검증 상태이며 보고서의 '검증 필요' 경고를 유지한다.

## 거절된 서버 비용 제안 (구매하지 않음)

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
