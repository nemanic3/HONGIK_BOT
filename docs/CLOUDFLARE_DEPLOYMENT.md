# 홍익졸업봇 Cloudflare 배포

## 실행 구조와 선택 이유

- 프런트엔드: Next.js 15.5.27 / React 19.1.0. 모든 사용자 데이터는 로그인 후 브라우저에서 API로 가져온다. 서버 렌더링에 사용자 데이터가 필요하지 않아 `output: export`로 Cloudflare Pages에 배포한다.
- 검수 화면: `/review?transcript_id=42`. 기존 `/review/42` 주소는 Pages의 `_redirects`로 연결한다. 임의 사용자 ID를 빌드 시 생성하지 않는다.
- API: Django 5.2 / DRF / SimpleJWT. Linux Docker에서 Gunicorn으로 실행한다. Pages Function은 `/api/*`만 HTTPS 원본 서버로 프록시한다.
- DB: 개발 SQLite를 유지하고, 운영은 새 PostgreSQL 16 비공개 볼륨을 사용한다. 기존 SQLite와 실제 계정·성적표는 자동 복사하지 않는다.
- 업로드: 인증된 소유자만 최대 5개, 합계 5 MiB의 PDF·PNG·JPEG를 업로드한다. PDF는 텍스트 추출, 스캔·이미지는 CPU 한국어 PaddleOCR를 사용한다. 원본, OCR 초안, 사용자 확정 자료가 분리된다.
- 비동기: Redis 7 / Celery, OCR 동시성 1, 작업자 메모리 상한 4 GiB. 웹 요청에서 OCR를 동기 실행하지 않는다.
- 파일: API와 OCR 작업자가 공유하는 비공개 Docker 볼륨. 파일 공개 URL은 없고 소유자 인증을 거친 미리보기 API만 제공한다.
- OCR 외부 연동: PaddleOCR 3.3.2 / PaddlePaddle 3.2.2 / PaddleX 3.3.13. 초기 준비 과정에서 모델을 다운로드한다. 운영 작업자는 외부 인터넷이 없는 네트워크에서 실행한다. 성적표를 외부 OCR/LLM API에 보내지 않으며 유료 OCR API 키가 필요하지 않다. Apple Vision은 macOS 로컬 개발용이다.

Cloudflare의 Python Workers에 Django 지원이 생겼지만 이 저장소를 그대로 옮길 수 있다는 뜻은 아니다. 현재 공식 D1/DO Django 백엔드는 트랜잭션을 지원하지 않으며 이 앱은 `transaction.atomic`과 `select_for_update`를 사용한다. Paddle의 네이티브 라이브러리·지속적인 Celery 작업자·파일 저장 또한 기존 Linux 환경이 필요하다. 해당 기능을 유지하기 위해 별도 서버를 선택한다.

공식 자료: [Pages 정적 Next.js](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/), [Django Workers와 DB 제약](https://developers.cloudflare.com/workers/languages/python/packages/django/), [Pages Git 연동](https://developers.cloudflare.com/pages/configuration/git-integration/), [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/get-started/).

## Cloudflare 설정

별도 Pages 프로젝트 `hongikbot`을 만든다. `nemanic-website`와 다른 서비스 설정은 수정하지 않는다.

| 설정 | 값 |
| --- | --- |
| GitHub | `nemanic3/HONGIK_BOT` |
| 프로덕션 브랜치 | `master` |
| 프로젝트 루트 | `frontend/team4-frontend-dev copy` |
| 빌드 명령 | `npm run build && node ../../deploy/verify-assets.mjs out` |
| 출력 | `out` |
| 사용자 지정 도메인 | `hongikbot.nemanic.dev` |
| 원본 서버 전용 도메인 | `hongikbot-origin.nemanic.dev` (서버 준비 후 전용 Tunnel에 연결) |

Pages 환경 변수:

| 이름 | 종류 / 값 |
| --- | --- |
| `NODE_VERSION` | 빌드, `22` |
| `PUBLIC_APP_ORIGIN` | Function, `https://hongikbot.nemanic.dev` |
| `API_ORIGIN` | Function, `https://hongikbot-origin.nemanic.dev`, 서버 준비 후 설정 |
| `HONGIK_PROXY_SECRET` | Function 암호화 secret, 서버와 같은 충분히 긴 난수 |
| `NEXT_PUBLIC_API_BASE_URL` | 선택 사항. 운영 기본값은 빈 문자열로 동일 도메인 `/api/` 사용 |
| `NEXT_PUBLIC_AUTH_REFRESH_PATH` | 선택 사항, 기본 `/api/users/refresh/` |

비밀 값에는 `NEXT_PUBLIC_` 접두사를 붙이지 않는다. 미리보기 도메인은 `PUBLIC_APP_ORIGIN`과 다르므로 운영 DB에 접근하지 못한다. API 원본이나 비밀 값이 없으면 503으로 차단한다. 파일은 정적 산출물에 포함되지 않으므로 Functions 한도 초과 시에도 공개될 파일이 없다.

## 서버 준비

2026-10-10 운영 호스트 선택: 사용자 Mac mini의 Docker Desktop (Linux ARM64). 유료 서버는 구매하지 않는다. `hongikbot` 운영 Compose 프로젝트는 개발 SQLite 및 `hongikbot-deploy-check` 테스트 볼륨과 분리한다. Mac 또는 Docker가 종료되면 백엔드가 중단된다. 현재 Mac의 시스템 절전은 꺼져 있으며 Docker에 약 8 GB 메모리가 할당되어 있다. Docker Desktop 로그인 시 자동 시작과 운영 배포 자동 갱신은 별도로 확인한다.

기존 Linux 서버가 있으면 추가 호스팅 구매 없이 사용 가능하다. 최소 시작 권장 사양은 2 vCPU / RAM 8 GiB / SSD 40 GiB이며 CPU OCR 처리량·업로드 보관량에 따라 조정한다. 유료 서버 생성은 비용 승인 후 진행한다. 로컬 Mac을 지속적으로 노출하는 배포는 기본 구성으로 사용하지 않는다.

1. 전용 `/opt/hongikbot` 디렉터리와 제한된 배포 계정을 준비한다. SSH 호스트 키를 검증하고 Docker Compose를 설치한다.
2. 저장소 코드를 배치한다. 사용자 DB·성적표·로컬 백업은 업로드하지 않는다.
3. `deploy/production/.env.example`을 루트 `.env.production`으로 복사하여 `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `HONGIK_PROXY_SECRET`을 각기 다른 난수로 설정한다. 파일 권한은 0600이다.
4. Cloudflare에서 전용 Tunnel을 만들고 `hongikbot-origin.nemanic.dev` → `http://api:8000` 경로만 설정한다. 토큰은 `deploy/production/secrets/tunnel-token`에 저장한다. 기존 Tunnel 경로를 변경하지 않는다.
5. `sh deploy/production/release.sh`를 실행한다. 새 운영 DB 마이그레이션, Django 보안 검사, 한국어 모델 준비, API·작업자·Tunnel 시작을 수행한다. API/DB/Redis 포트는 인터넷에 공개하지 않는다.
6. Pages의 운영 `API_ORIGIN`과 암호화 `HONGIK_PROXY_SECRET`을 설정하고 다시 배포한다. 준비 전에는 API가 503을 반환하는 것이 정상이다.
7. 합성 계정과 가짜 성적표로 HTTPS에서 회원가입 → 로그인 → 다중 업로드 → OCR → 검수/수정 → 확정 → 졸업 보고서 → 토큰 갱신/로그아웃을 확인한다. 다른 계정에서 성적표·미리보기 접근이 차단되는지도 확인한다.

서버 변수는 Compose에 명시되어 있다: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ORIGINS`, `DJANGO_CSRF_ORIGINS`, `DJANGO_DB_ENGINE`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `DJANGO_MEDIA_ROOT`, `DJANGO_REQUIRE_PROXY_SECRET`, `HONGIK_PROXY_SECRET`, `TRANSCRIPT_PROCESSING`, `TRANSCRIPT_IMAGE_OCR_PROVIDER`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`. 선택 OCR 설정: `OCR_CPU_THREADS`.

## GitHub 자동 배포

Mac mini에서는 SSH 배포 workflow를 활성화하지 않는다. 사용자 LaunchAgent `dev.nemanic.hongikbot`가 5분마다 master의 최신 커밋과 GitHub `Verify deployment` push 검사 성공을 확인한다. 운영 전용 체크아웃은 `~/Library/Application Support/HongikBot/repository`이다. Desktop에서 LaunchAgent 실행은 macOS 개인정보 보호로 차단되어 운영 체크아웃을 별도로 마련했다. 성공한 커밋만 그 안의 `.production-runtime/releases/<SHA>`에 Git archive로 배치한 뒤 기존 운영 볼륨을 사용하는 release 스크립트를 실행한다. 개발 작업 파일은 덮어쓰지 않는다. 로컬 `gh` 로그인과 네트워크가 필요하며, Mac 로그인 후 Docker가 준비되면 실행된다. 수동 실행: `HONGIK_REPOSITORY_ROOT="$HOME/Library/Application Support/HongikBot/repository" sh "$HOME/Library/Application Support/HongikBot/macmini-update.sh"`. 로그는 운영 체크아웃의 `.production-runtime/update.log`와 `update-error.log`, 백업은 `.production-runtime/backups`에 저장한다. Mac의 전원 종료 및 사용자 로그아웃 시 서비스가 중단될 수 있다.

Pages는 `master` 커밋마다 웹과 Function을 자동 배포한다. `.github/workflows/verify.yml`은 프런트 테스트·정적 빌드·비공개 파일 제외 및 합성 Django 테스트를 검증한다.

백엔드는 `Verify deployment`의 성공한 master push 이후 SSH로 전용 서버에 코드만 전달한다. `.github/workflows/deploy-backend.yml`은 기본 비활성 상태이고 서버를 준비한 뒤 다음을 설정해야 한다.

- 저장소 변수 `HONGIK_BACKEND_ENABLED=true`.
- `hongikbot-production` GitHub Environment의 secrets: `HONGIK_BACKEND_HOST`, `HONGIK_BACKEND_USER`, `HONGIK_BACKEND_SSH_KEY`, `HONGIK_BACKEND_KNOWN_HOSTS`.
- 운영 Django·DB·Tunnel 비밀 값은 서버에만 두고 GitHub 코드 아카이브에 포함하지 않는다.
- SSH는 검증한 known_hosts와 StrictHostKeyChecking을 사용한다. 업데이트 전 API와 OCR를 멈추고 DB·파일 백업 후 마이그레이션한다. 무중단 배포 구성은 아니다.

## 개인정보, 백업, 보관

배포 이미지의 `.dockerignore`는 SQLite, 미디어, `.env`, 백업을 제외한다. 정적 산출물은 `deploy/verify-assets.mjs`로 검사한다. API 응답은 private/no-store이며 원본 서버는 프록시 비밀 값이 없으면 403으로 차단한다. 성적표 소유권은 기존 JWT 기반 API에서 별도로 검사한다.

이 작업에서 기존 추적 DB·미디어를 Git 추적에서 제외하고 로컬 원본은 보존했다. 저장소는 공개이므로 **과거 커밋의 사용자 데이터는 여전히 별도의 정리 대상**이다. 제거 커밋만으로 과거 노출이 복구되지 않는다. 이력 재작성·강제 push·GitHub 캐시 정리는 별도 승인이 필요하고, 기존 개발용 서명키를 운영에 재사용하지 않는다.

원본 성적표·OCR 데이터는 현재 자동 삭제 없이 보관한다. 보관 기간과 사용자 삭제 정책은 운영자가 결정해야 한다. 재시도끼리 파일을 공유하므로 단순 파일 삭제로 처리하면 안 된다. `release.sh` 백업은 서버의 `.backups/production`에 0600으로 저장한다. 운영 전에 암호화된 외부 백업과 복원 검증을 추가한다. 운영 볼륨에서 `docker compose down -v`를 실행하지 않는다.

## 합성 데이터 검증

`compose.test.yaml`은 `hongikbot-deploy-check`처럼 별도 프로젝트 이름, 새 DB·미디어 볼륨, localhost 18082만 사용한다. 실제 개발 SQLite에 migrate를 실행하지 않는다. 운영 Tunnel은 테스트에서 시작하지 않는다.

```sh
cd 'frontend/team4-frontend-dev copy'
npm test
npm run build
node ../../deploy/verify-assets.mjs out
cd ../../backend
.venv/bin/python -B manage.py test --noinput
```

검증 결과와 실제 공개 설정 상태는 `CLOUDFLARE_VERIFICATION.md`에 기록한다.
