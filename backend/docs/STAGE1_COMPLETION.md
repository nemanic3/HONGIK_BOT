# 1단계 완료 보고 (실제 DB 적용 보류)

## 완료 범위

사용자 결정에 따라 코드·테스트 DB·기존 DB 사본 검증까지 완료했다. 실제 backend/db.sqlite3에는 마이그레이션을 적용하지 않았다. 따라서 현재 실제 DB의 drbol_rules 열 불일치는 적용 전 상태이며, 새 코드를 실제 DB로 구동하는 것은 아직 승인되지 않은 별도 작업이다.

- 모델/마이그레이션/기존 SQLite 비교: drbol_rules 누락 복구용 nullable 열 추가. 기존 drbol_areas NOT NULL 구조 유지. 추가 방향 SQL은 열/테이블 삭제 없이 열 및 인덱스만 추가한다.
- 졸업요건 JSON: 과목 참조 객체 형식 통일, 숫자 문자열 학점 검증, 추가 메타데이터 보존, 최초 원본 JSON 스냅샷 legacy_data.
- 공통 과목 계약: schema_version=1, 문자열 과목코드, 유한/음수 아닌 credit, OCR 초안과 확인용 검증 분리. 원본 셀을 과목으로 추정하지 않는다.
- 성적표: raw OCR/구조화 초안/사용자 확정 문서·시각·확인자 분리. 기존 parsed_data 유지. 확정 데이터 우선, 빈 확정 목록도 유효.
- 입학연도: User.admission_year와 current_year 독립. 학과+정확한 입학연도 조회. 레거시 사용자는 학과 요건이 하나인 경우만 fallback.
- 분석/학기/파싱 API 입력 출처 연결. OCR task의 결과 보관 경로 연결 (실제 OCR provider 검증은 아님).
- source_reference/verified_at: 공식 검증 기록을 위한 필드만 추가. 기존 수치를 공식 기준으로 승격하거나 새로운 정책을 생성하지 않음.

## 실행 검증

- manage.py test --verbosity 1: 30 tests, OK.
- manage.py check: System check identified no issues (0 silenced).
- manage.py makemigrations --check --dry-run: No changes detected.
- pip check: No broken requirements found.
- 기존 DB 사본에 신규 마이그레이션 6개 적용: 모두 OK.
- verify_stage1_db.py 비교: 모든 기존 행/기존 필드 보존, 변경 JSON의 원본 스냅샷 보존, 원래 요구학점 수치 보존, integrity_check=ok, foreign_key_check=ok.
- 원본 DB와 적용 전 백업의 모든 테이블 행/값 및 sqlite_master 스키마 동일 확인. 원본 DB 적용 없음.
- 자동화 테스트는 신규 테스트 DB 생성부터 데이터 마이그레이션의 정·역방향을 포함한다. 이후 수정된 데이터는 손실 가능성이 있는 역방향 변환을 중단하도록 구현했다.
- core Ruff(E4/E7/E9/F) 비교: 기존 29건→현재 22건, 신규 진단 0건 (리뷰 수정 직전 검사). 전역 Ruff 전체 규칙은 통과하지 않았으며 기존 및 스타일 진단 정리는 다음 단계와 분리한다.

## 독립 리뷰와 수정

독립 리뷰는 신규 회귀 3건을 재현해 최초 승인하지 않았다. 수정 담당 서브에이전트는 provider HTTP 429로 중단됐고, 부모 에이전트가 회귀 테스트 실패를 확인한 후 직접 수정했다.

1. stale requirement 부분 저장 시 관계없는 과목 필드 덮어쓰기 → update_fields에서 실제 요청한 과목 필드만 저장.
2. 동일 raw OCR 재시도로 구조화 결과가 null이 되는 문제 → 새 구조화 결과가 없으면 기존 ocr_data 유지.
3. 확정 성적표 재처리로 OCR 상태가 변경되고 결과 endpoint가 404가 되는 문제 → 확정 성적표 task 재시도는 무변경 반환; 확정 결과는 OCR 상태와 독립적으로 반환.

이 세 문제의 영구 회귀 테스트 및 전체 30개 테스트가 통과했다. 이후 최종 수정본의 독립 재리뷰(deleg_c96f857c)가 완료되어 passed=true, 차단 보안·논리 오류 없음으로 보고됐다. 리뷰어도 실제 DB 대신 메모리 DB에서 전체 30개 테스트를 독립 실행해 통과했다. 남은 비차단 항목은 analysis/tests.py EOF 빈 줄 경고다. 실행 중인 서브에이전트 작업은 없다.

## 백업

적용 전 백업: .backups/db-before-stage1-final-20261009-035903.sqlite3
검증 사본: .backups/db-stage1-probe-20261009-035903.sqlite3
개인정보를 포함하므로 Git 제외, 디렉터리 0700/파일 0600. 운영 DB 복구/실제 적용은 별도 승인 후 진행한다.

## 남은 문제

공식 요건·인증/비인증·입학연도별 경과조치 검증, 중복/재수강/P·F 인식과 종합·상세 API 판정 일치, 사용자 수정·확정 HTTP API, 업로드 검증, 실제 OCR·PDF 페이지 처리, Celery/Redis 통합, 프론트 연결은 미완료다. 기존 자격증명·Git 추적 DB/media 및 API 소유권 검토도 운영 전 필요하다.

Git commit/push 없음. 사용자 추가 PDF 및 IDE 상태는 손대지 않았다.

## 변경 파일

- .gitignore
- backend/analysis/migrations/0002_restore_requirement_schema.py
- backend/analysis/migrations/0003_requirement_metadata.py
- backend/analysis/migrations/0004_normalize_course_references.py
- backend/analysis/models.py
- backend/analysis/services.py
- backend/analysis/test_migrations.py
- backend/analysis/tests.py
- backend/analysis/views.py
- backend/common/__init__.py
- backend/common/course_schema.py
- backend/common/migration_schema_v1.py
- backend/common/transcript_data.py
- backend/docs/STAGE1_DATA_CONTRACT.md
- backend/requirements-dev.txt
- backend/requirements.txt
- backend/scripts/verify_stage1_db.py
- backend/semesters/views.py
- backend/transcripts/migrations/0003_separate_course_data.py
- backend/transcripts/migrations/0004_archive_legacy_data.py
- backend/transcripts/models.py
- backend/transcripts/tasks.py
- backend/transcripts/test_course_schema.py
- backend/transcripts/test_migrations.py
- backend/transcripts/test_tasks.py
- backend/transcripts/tests.py
- backend/transcripts/views.py
- backend/users/migrations/0002_admission_year.py
- backend/users/models.py
- backend/users/serializers.py
- backend/users/tests.py
