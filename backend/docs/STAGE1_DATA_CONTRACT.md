# 1단계 데이터 계약

범위: 데이터 구조·마이그레이션·입력 출처·입학연도 조회. OCR 정확도 개선, 사용자 확정 HTTP API, 공식 졸업 판정 통합은 다음 단계다.

## 공통 과목 문서 (schema_version=1)

```json
{
  "schema_version": 1,
  "courses": [{
    "code": "001009",
    "name": "예시 과목",
    "credit": 2.5,
    "grade": "A+",
    "semester": "1-1",
    "type": "교양",
    "major_field": "교양필수",
    "retake": false,
    "academic_year": 2025,
    "term": "1",
    "aliases": []
  }]
}
```

위 과목은 형식 예시이며 홍익대학교 공식 요건이나 실제 수강 데이터가 아니다.

- code는 문자열이다. 앞자리 0, 과목명, 별도 메타데이터를 보존한다.
- credit는 음수 아닌 유한 숫자 또는 초안에서는 null이다. 숫자 문자열은 변환하고 boolean, NaN, 무한대, overflow/underflow는 거절한다.
- 초안의 불명확한 값은 채우지 않는다. 확인용 문서에는 name/credit/grade/semester/type이 필요하다.
- academic_year는 실제 수강연도, semester는 기존 API의 학기 문자열, admission_year는 사용자의 입학연도다. 서로 추론하지 않는다.
- 원본 OCR 문자열·2차원 셀 배열은 과목으로 추정하지 않는다. 초안·원본 데이터가 불충분하면 분석 API는 기존 오류 경로를 사용한다.
- 알 수 없는 문서 버전과 잘못된 객체 타입은 거절한다. 빈 확정 courses 배열도 유효하고 우선한다.

## 졸업요건

- 기존 year 필드명은 유지하되 의미는 입학연도다. (major, year) 기존 유일성도 유지한다.
- 7개 과목 목록은 과목 참조 객체 배열, drbol_courses는 영역명→과목 참조 객체 배열로 정규화한다. 비어 있는 선택 목록은 [] 또는 {}다.
- 문자열 과목명도 참조 객체로 변환한다. code/name 중 하나는 필요하며 semester/aliases와 추가 메타데이터를 보존한다.
- legacy_data는 변환 전 JSON 스냅샷이다. 요구학점 수치는 변경하지 않는다.
- drbol_rules 열을 추가하지만 기존에 없던 영역 규칙/요구학점은 생성하지 않는다. 기존 null 규칙은 null로 유지한다.
- source_reference/verified_at는 공식 출처 확인을 기록할 기반이다. 기존 요건이 자동으로 검증되지는 않는다.
- 새 졸업요건의 기본 수치는 기존 모델의 값이므로 공식 검증 전 운영에 사용하면 안 된다.

## 성적표 출처

- parsed_data: 기존 호환 버퍼. 기존 값은 데이터 마이그레이션에서 그대로 유지한다.
- ocr_raw_data: OCR 원본. 기존 parsed_data를 복사하되 사용자 확인으로 간주하지 않는다.
- ocr_data: 스키마로 변환 가능한 OCR 초안 문서. 변환 불가능하면 null이다.
- confirmed_data/confirmed_at/confirmed_by: 사용자가 확정한 문서·확인 시각·확인자. 모델 서비스 confirm_courses는 소유자만 허용한다.
- 입력 우선순위: confirmed_data → ocr_data → parsed_data. 유효하지 않은 상위 출처에서 하위 출처로 조용히 fallback하지 않는다.
- get_analysis_document는 분석에 필요한 필드를 확인한다. 실제 사용자 확인 완료를 필수로 하는 운영 정책은 다음 단계에서 결정한다.
- record_ocr_result는 기존 OCR 원본을 다른 값으로 덮어쓰지 않으며, 확정된 성적표를 재처리하지 않는다. 새 업로드는 새 Transcript로 관리한다.
- 기존 completed 상태는 done으로 통일하고 legacy_status에 이전 상태를 보존한다.
- 기존 parsed 결과 endpoint는 확정 문서를 우선 반환한다. 원본 셀/문자열은 JSON 값으로 반환하며 깨져 있던 텍스트 렌더링 분기는 제거했다.

## 입학연도 조회

- User.admission_year는 nullable이며 current_year와 독립적이다. 가입/사용자 수정 serializer에서 선택적으로 받는다.
- 입학연도가 있으면 학과+정확한 입학연도만 조회한다. 다른 연도 요건을 대신 선택하지 않는다.
- 연도 없는 기존 사용자에게는 해당 학과 요건이 정확히 하나인 경우에만 호환 fallback한다. 여러 요건이면 조회 실패로 반환한다.
- 기존 사용자 입학연도는 학번에서 추정하거나 자동 입력하지 않는다.

## 마이그레이션/검증

backend에서 실행:

```sh
.venv/bin/python -B manage.py test --verbosity 1
.venv/bin/python -B manage.py check
.venv/bin/python -B manage.py makemigrations --check --dry-run
.venv/bin/python -B manage.py migrate --plan
```

먼저 SQLite backup API로 DB 백업을 생성한 후 사본에 적용하고, scripts/verify_stage1_db.py BEFORE.sqlite3 AFTER.sqlite3로 모든 기존 행/필드와 스냅샷·무결성을 비교한다. 개인정보 값은 출력하지 않는다.

- 적용 방향은 nullable 열 추가, 인덱스 생성, 원본 보존형 JSON/상태 변환이다. 기존 열·테이블 삭제가 없다.
- 데이터 마이그레이션 역방향은 변경 없는 데이터만 되돌린다. 마이그레이션 이후 수정된 데이터는 손실을 막기 위해 오류로 중단한다.
- 스키마 추가 자체의 역방향은 추가 열을 삭제할 수 있으므로 실제 DB에서 자동 rollback하지 않는다. 운영 복구는 서버를 정지한 상태에서 검증된 전체 백업을 이용해 별도 승인으로 진행해야 한다.
- common/migration_schema_v1.py는 이 릴리스의 역사적 변환 규칙이다. 릴리스 후 변경하지 말고 새로운 버전 파일을 만든다.
- bulk_create/QuerySet.update는 Django save/clean을 우회한다. 일반 데이터 쓰기는 모델 메서드/검증된 서비스 경로를 사용한다.

## 남은 운영 차단 요인

공식 졸업요건 검증과 API 간 판정 통합(필수 교양, 영역 예외, 재수강/중복/P·F), 업로드 형식·5MB 제한, 데이터 소유권 검토, OCR provider import/실제 PDF 페이지 처리, Celery·Redis 실행, 수정·확정 API와 프론트 연결은 아직 완료되지 않았다. 기존 소스의 자격증명과 이미 Git에 추적된 DB/media 파일은 별도 보안 정리가 필요하다. .gitignore만으로 추적이 해제되지는 않는다.
