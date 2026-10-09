# 캡처 기반 서비스 후속 검증 — 2026-10-09

## 범위와 기존 기능 재사용

기준 커밋 `fd6b425`의 Django/Next.js 구조, 사용자 JWT 인증, 입학연도·공학인증 프로필, 버전별 졸업 규칙, 원본/OCR/확정 데이터 분리, 사용자 확인 API와 분석 엔진, 업로드·검토·대시보드 화면을 유지했다.
기존 보고의 112/34개 수치를 재사용하지 않았다. 작업 시작 시 현재 코드에서 백엔드 114개, 프론트엔드 36개 테스트 통과를 확인했다.
학교 계정 자동 로그인, 확장 프로그램, 학교 API 연동은 추가하지 않았다.

## 구현 변경

- `transcripts/spatial.py`: 좌표 기반 두 단 분리, 표 머리글·학기 구분, 줄바꿈 과목명, 빈 셀, 재수강/학기재수강 표시와 출처 좌표.
- 겹친 캡처는 학수번호+학기+모든 과목 값이 같고 다른 캡처/페이지에 있는 경우에만 병합하고 모든 출처를 보존한다. 다른 학기는 삭제하지 않는다. 같은 학기라도 값이 다르면 충돌 후보로 남긴다.
- 잘린 후속 캡처는 이전 열 위치를 제한적으로 재사용한다. 학기가 보이지 않으면 null과 확인 사유를 남긴다. 읽지 못한 학수번호 행과 하단 잘림 경고를 표시한다.
- Paddle 한국어 모바일 모델 어댑터, 긴 이미지 분할, EXIF 방향, PDF 내장 텍스트 좌표 보존. 추론 결과의 A/O/0 등을 임의 치환하지 않는다.
- 누락되어 있던 `core/celery.py` 초기화 복구. API와 작업자의 같은 Django 설정 사용, 비동기 상태 조회, 제한 시간, 일시 오류 재시도, 실패 작업 재시도 API.
- 소유자 전용 원본 미리보기 API. 파일명/저장 경로를 노출하지 않으며 PDF 각 페이지 비교 가능.
- 검토 화면: 학기별 보기, 원본 위치 표시, 불확실/중복/재수강 사유, 직접 수정·추가·삭제, 인정 포함/제외 선택. JSON은 고급 편집으로 접었다.
- 코드가 다르고 이름이 같은 기록도 동일과목/대체과목 근거가 없으면 확인 대상으로 남겨 임의 합산을 막는다.
- 재수강: 자동으로 최신/최고 성적을 선택하지 않는다. 중복 인정은 막고 사용자가 선택한 하나만 잠정 계산한다. F/NP는 합산하지 않는다. 제외한 옛 기록은 빈 성적/학점을 채워 만들지 않아도 보존한다.
- 근거 문서와 페이지가 필수인 `course_relations` 스키마: `same_course`는 동일 식별자, `replacement`는 별개 식별자로 유지한다. 검증되지 않은 실제 코드 변경 관계는 추가하지 않았다. 대체과목의 필수 충족은 별도 명시 규칙이 필요하다.
- 대시보드에 계산 제외 기록을 표시하고, 확정 후 다시 검토·수정할 수 있다. OCR 불완전 자료는 검증 필요를 유지한다.
- 기존 DB 경로와 별도로 환경변수로 DB/미디어 경로 지정. Docker 서비스 데이터는 전용 새 볼륨 사용.

## 실제 실행 검증

실행 주소: 웹 `http://127.0.0.1:3001`, Docker API `http://127.0.0.1:8001`.

- 브라우저에서 합성 계정 회원가입·로그인 성공.
- 합성 PNG 두 장 한 번에 업로드 → 실제 Celery/PaddleOCR 처리 → 검토 화면 성공.
- 원본 12개 행 → 학기별 9개 기록. 겹친 3개 행은 출처 2개씩 유지, 다른 학기 동일 과목 2개 기록은 재수강 후보 유지.
- 줄바꿈 이름의 실제 OCR 오인식 1건을 원본과 비교해 직접 수정. 원본 행 강조, 학기 필터, 재수강 포함/제외 선택 후 확정 성공.
- 대시보드 총 인정 24학점과 수정한 과목명, 3개 학기 표시 확인. 공식 확정 판정 대신 검증 필요 표시.
- 실제 HTTP에서 재확정으로 한 행 3→2학점 변경 시 총계 24→23 즉시 재분석.
- 다른 계정으로 상세·원본·확정·재시도·분석 접근 모두 404 차단.
- 가짜 PNG 400 거절. 빈 PNG 실제 OCR 실패, 재시도 새 리소스 생성과 이전 원본 보존 확인.

## Docker / 실제 OCR

- Python 3.11 / PaddlePaddle 3.2.2 / PaddleOCR 3.3.2 / PaddleX 3.3.13 Linux ARM64 이미지 빌드 성공.
- `PP-OCRv5_mobile_det` + `korean_PP-OCRv5_mobile_rec`; 외부 인터넷 없는 작업자에서 캐시 모델로 처리 성공.
- 실측 합성 두 장 비동기 처리: 약 23.42초(작업자 첫 모델 초기화 포함). 이전 따뜻한 작업자는 약 6초. 성능 보장 수치가 아니며 동시 부하 미검증.
- 1900×2700 긴 합성 캡처: 2개 타일, 12행 추출, 약 27.37초(별도 프로세스 모델 초기화 포함).
- 기존에 사용자가 제공한 실제 캡처의 로컬 Paddle 결과 재파싱: 단일 표 6행, 두 단 표 27행. 단일 표에는 이수구분 열이 없어 6행 모두 확인 대상, 두 단 표 17행 확인 대상 및 학점 1개 미인식. 실제 성적표 전체의 필드 정확도/누락률을 정답지로 측정한 것은 아니다.

## 규칙 근거와 한계

기존 분석 문서와 규칙 JSON의 PDF/인쇄 페이지를 유지한다. 제공 PDF는 파일명에 `(안)`이 있어 공식 최종본으로 인증하지 않았다.
PDF 3쪽(책자 1쪽)은 폐지·대체과목이 동일과목이 아님을, PDF 4쪽(책자 2쪽)은 명칭 변경 동일과목을 설명한다. 실제 과목별 변경 관계와 재수강 성적 선택, 학기재수강, 취득시점·면제·졸업논문 인정은 추가 확인이 필요하다.

OCR 높은 신뢰도도 정확함을 보장하지 않는다. 합성 예제에서도 '프로그래밍'이 '브로그래밍'으로 읽혔다. 좌표 없는 복잡한 표, 심한 잘림, 회전/기울기, 학기 제목 누락, 같은 행의 서로 다른 오인식은 수동 확인이 필요하다. 병합은 보수적이며 충돌 후보를 자동 삭제하지 않는다.

지원 규칙은 기존 서울 컴퓨터공학과 범위이다. 다른 학과·캠퍼스의 졸업 가능 여부를 판정하지 않는다. 실제 전체 학생 성적표에 대한 정량 정확도 검증, 동시 사용자 부하, 비 ARM64 배포는 미완료.

공개 배포 전: 공식 최종 교과과정·정오표와 세부 인정 정책 확인, 다양한 동의된/비식별 성적표 정답 데이터 평가, 프로덕션 서버/HTTPS, 요청 제한, 백업복원, 원본 보존·삭제 정책이 필요하다. 자세한 실행·보관 정책은 `deploy/ocr/README.md` 참고.

## 데이터 보존

이번 작업은 원본 SQLite DB를 읽기만 했고, 검증 계정·업로드·마이그레이션은 새 Docker 볼륨 또는 자동 테스트 DB에만 생성했다. 이전 작업에서 이미 존재하던 DB 변경과 Git 변경은 유지했다. Git stash를 적용·삭제하지 않았고 commit/push 및 외부 배포는 하지 않았다.

## 최종 자동화 검증

- 백엔드: **138개 통과** (`backend`에서 `python manage.py test --noinput`). 실제 macOS Vision 합성 이미지 시험도 포함된다. Linux에서는 해당 macOS 전용 시험이 제외되며 Paddle의 실추론은 위 Docker 통합 검증으로 확인했다.
- 프론트엔드: **38개 통과**, TypeScript 타입 검사 및 Next.js 프로덕션 빌드 성공.
- `makemigrations --check --dry-run`: 변경 없음. `git diff --check`: 통과.
- Docker `pip check`: 충돌 없음. 마지막 코드 반영 후 HTTP 통합 검증 재실행도 통과(두 장 OCR 약 22.33초).
- 작업 전후 기존 `backend/db.sqlite3` SHA-256 동일. 기존 stash 1개 유지.

## 이번 변경 파일 목록

루트: `.dockerignore`, `.gitignore`.

백엔드:
- `backend/core/{__init__.py,celery.py,settings.py}`, `backend/requirements.txt`
- `backend/transcripts/{spatial.py,paddle_provider.py,parser.py,reader.py,tasks.py,views.py,urls.py}`
- `backend/common/course_schema.py`, `backend/analysis/{engine.py,policy.py}`
- `backend/transcripts/{test_multicapture.py,test_api.py}`, `backend/analysis/test_recognition.py`

프론트엔드(접두 경로 `frontend/team4-frontend-dev copy/`):
- `app/review/[id]/page.tsx`, `app/upload/page.tsx`, `app/mypage/page.tsx`
- `app/mypage/components/TakenCourses.tsx`
- `lib/contracts.ts`, `lib/types.ts`, `tests/contracts.test.mjs`, `tests/frontend-review.test.mjs`
- `next.config.mjs`, `tsconfig.json`, `next-env.d.ts`(검증 서버 빌드 출력 분리·자동 생성 관련)

구성·문서:
- `deploy/ocr/{Dockerfile,compose.yaml,README.md}`
- `docs/FINAL_VERIFICATION.md`, `docs/SCREENSHOT_SERVICE_VERIFICATION.md`

이전 작업에서 이미 있던 `backend/db.sqlite3`, Vision Swift/파서 시험, API 시간제한·업로드 흐름, 대시보드 CSS, `start-local.command`, `tools/ocr-benchmark` 등의 미커밋 변경은 그대로 유지했다. `.env.ocr`는 Git 제외된 로컬 비밀키 파일이며 변경 목록/로그에 값을 노출하지 않는다.
