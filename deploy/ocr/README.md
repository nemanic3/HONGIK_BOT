# 로컬 Docker OCR 서비스

기존 Django/Next.js를 재사용한다. 학교 로그인·확장 프로그램·학교 API는 사용하지 않는다.
PaddleOCR 호출 요금은 없다. 컴퓨터/서버 CPU·메모리·저장공간은 필요하다.

## 구성과 검증 환경

- Python 3.11, PaddlePaddle 3.2.2, PaddleOCR 3.3.2, PaddleX 3.3.13.
- 명시적으로 `PP-OCRv5_mobile_det` + `korean_PP-OCRv5_mobile_rec` 선택.
- macOS ARM64의 Docker Linux/aarch64에서 빌드·추론·Celery 처리를 검증했다. 다른 아키텍처는 미검증.
- API: `http://127.0.0.1:8001`. 작업자: 1개, CPU 4개/메모리 4GiB 제한.
- Redis와 작업자는 외부 인터넷이 없는 내부 네트워크에 둔다. API만 localhost에 공개한다.
- DB와 업로드는 새 `service-state` 볼륨에 저장한다. 맥북의 `backend/db.sqlite3`를 마운트하지 않는다.
- Redis 작업 대기열은 별도 AOF 볼륨에 저장한다. 실패 후 재시도는 새 성적표 리소스를 만들고 원본을 공유한다.

## 처음 실행

프로젝트 루트에서 실행한다. Docker Desktop은 먼저 켜야 한다.

```sh
docker build -t hongik-service-ocr:local -f deploy/ocr/Dockerfile .
docker volume create hongik-ocr-models
# 모델만 내려받는 준비 단계. 학생 파일을 마운트하지 않는다.
docker run --rm -v hongik-ocr-models:/root/.paddlex hongik-service-ocr:local python -c 'from transcripts.paddle_provider import model; model()'
```

`.env.ocr`에는 `DJANGO_SECRET_KEY`를 충분히 긴 난수로 설정한다. 파일 권한은 600으로 제한하고 Git에 추가하지 않는다. 이번 맥북 검증에는 이 파일이 이미 준비되어 있다. 서버와 작업자는 같은 키를 사용해야 한다.

다음 마이그레이션 명령은 **새 Docker 볼륨의 DB 초기화용**이다. 기존 운영 볼륨을 재사용하는 경우 먼저 백업·사본 검증 및 승인이 필요하다.

```sh
docker compose -p hongik-service-check --env-file .env.ocr -f deploy/ocr/compose.yaml run --rm backend python manage.py migrate --noinput
docker compose -p hongik-service-check --env-file .env.ocr -f deploy/ocr/compose.yaml up -d
cd 'frontend/team4-frontend-dev copy'
NEXT_DIST_DIR=.next-service-check NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1 --port 3001
```

웹사이트: `http://127.0.0.1:3001`. 원래 3000/8000 개발 환경과 DB가 다르다.
종료는 `docker compose ... stop`으로 한다. 데이터가 필요한 동안 `down -v`를 실행하지 않는다.

## 처리·실패·보관

- PDF/JPG/PNG, 한 번에 1~5개, 합계 5MiB, 이미지/페이지 20MP 이하. PDF는 파일당 최대 50쪽.
- EXIF 방향 보정. 폭 2400px 초과만 비례 축소하고, 긴 이미지는 높이 2000px/겹침 160px로 분할하여 OCR한다.
- EXIF가 없는 임의의 90도 회전·기울어진 촬영은 보장하지 않는다. 정방향 화면 캡처 권장.
- 작업자는 600초 소프트/660초 하드 제한. 연결/입출력 오류는 페이지당 한 번 추가 시도한다. 빈 결과는 실패로 기록한다.
- 실패 또는 15분 이상 멈춘 대기/처리 작업은 소유자만 재시도할 수 있다. 같은 원본은 한 시간에 최대 3개 작업. 기존 결과·파일은 덮어쓰지 않는다.
- 업로드 파일은 공개 URL로 제공하지 않는다. 소유자 인증 후에만 축소 미리보기를 제공하며 `private, no-store`를 설정한다.
- 작업 로그에는 성적표 본문을 출력하지 않는다. OCR/미리보기용 변환 이미지는 메모리에서 처리한다.
- **현재 보관 정책은 원본·OCR·확정 데이터 보존이며 자동 삭제는 꺼져 있다.** 재시도 기록끼리 원본 파일을 공유하므로 단순 파일 삭제는 금지한다.
- 공개 서비스 전에 원본 보존기간/사용자 삭제/백업 만료 정책을 고지하고 구현해야 한다. 권장 검토안: 확정 후 원본 30일 보관, 만료 전에 안내, 전체 참조가 없어질 때 물리 삭제. 이 기간은 확정 정책이 아니며 현재 적용되지 않는다.

## 공개 배포 전

현재 Compose는 **로컬 검증용 runserver**이다. 인터넷에 그대로 공개하지 않는다.
프로덕션 WSGI 서버·HTTPS·`DJANGO_DEBUG=0`·명시적 호스트/CORS·비밀키 관리, 비특권 실행, 사용자별 OCR 요청 제한·큐 모니터링·백업 복원·업로드 삭제 정책이 필요하다. SQLite 다중 작업자 동시 쓰기/부하도 검증되지 않았다.
모델 캐시가 없으면 내부 네트워크의 작업자는 모델을 다운로드하지 못한다. 준비 단계에서 모델 캐시를 먼저 채운다.
