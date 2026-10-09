# 최종 검증 기록

## 범위와 원본 보존

이 작업은 데이터 계약·마이그레이션 코드와 **사본 DB 검증**, 제공 PDF 분석, 검증필요 기반 분석 엔진, 업로드→검수→확정→대시보드 연결을 대상으로 한다. **원본 `backend/db.sqlite3`에는 migrate/import를 실행하지 않았다.** 실제 사용자 계정과 원본 성적표 파일을 수정하거나 삭제하지 않았다.

- 원본 DB SHA-256: `ed94d2232e0a6dea96b902c92c9749f518e022d5ccd75294ffc6f1850dd206e9` — 작업 전 기준과 일치.
- 제공 PDF SHA-256: `9d96c675c8df7d3f3a75971da582975e624dfda33a10f194774942216a17e5a5` — 작업 전 기준과 일치.
- 제공 PDF 실제 페이지 수: 237. 본문 근거는 `graduation-requirements-analysis.md`의 PDF/인쇄 이중 쪽수를 사용한다.
- 사본에 모든 추가 마이그레이션 적용 후 `integrity_check`·`foreign_key_check` 및 모든 기존 열/행 보존 검사를 통과했다. 새 규칙 모델의 Django content type/기본권한 추가만 별도로 허용하며, 기존 메타데이터 행 변경은 허용하지 않는다.
- 보존된 원본 주요 행 수: 사용자2, 기존 졸업요건1, 성적표2, 성적표 페이지1. 개인 행 내용은 보고서에 출력하지 않는다.

## 기능별 변경

| 기능 | 주요 경로 | 검증 범위 |
|---|---|---|
| 레거시 구조 복구·원본 snapshot | `backend/analysis/models.py`, `analysis/migrations/0002–0004`, `common/migration_schema_v1.py` | 모델/DB 차이, 정규화 전 원문, 소수·숫자경계, 역방향 데이터 보존 |
| 공통 과목 문서 | `backend/common/course_schema.py`, `transcript_data.py` | 학수번호 문자열·선행0, 메타데이터, finite credit, 미확정 입력 차단 |
| OCR/확정 분리 | `backend/transcripts/models.py`, `migrations/0003–0004` | raw/draft/confirmed 우선순위, 빈 확정목록, 재시도·동시확정 보존 |
| 입학연도·인증과정 | `backend/users/models.py`, `serializers.py`, `views.py`, `migrations/0002–0003` | 학년과 분리, 명시 입력, 프로필 수정/소유자 |
| 버전형 규칙·엔진 | `backend/analysis/{models,policy,engine,report_views}.py`, `data/hongik_cs_2026.json`, `management/commands/load_curriculum_rules.py` | 과정별 기준, 지정과목 학점, 영역, SW 슬롯, 잘못된 규칙·overflow 차단 |
| 업로드/추출/확정 API | `backend/transcripts/{serializers,views,urls,tasks,reader,parser}.py` | 파일 검증, ID 전달, 소유권, 실제 PDF 추출, queue 장애와 수동복구 |
| 선택형 로컬 OCR | `backend/transcripts/vision_provider.py`, `scripts/vision_ocr.swift` | 실제 Vision 인식, 플랫폼/도구·시간·입출력 제한, 임시파일 보안 |
| 프론트 통합 | `frontend/team4-frontend-dev copy/lib`, `app/review/[id]`, `app/mypage`, 업로드·가입·프로필 컴포넌트 | 단일 분석응답, 메타데이터 유지, nullable 초안 검수, 인증 경쟁·탭 전환 |
| 보안/재현성 | `backend/core/settings.py`, requirements, frontend package/lock, `.gitignore` | 환경변수 signing key, production key 필수, 취약 의존성 교체·민감자료 제외 |

## 실행한 검증

다음 결과는 실제 도구 실행 결과다. backend와 frontend 각각 해당 디렉터리에서 실행했다.

| 명령/검증 | 결과 |
|---|---|
| `.venv/bin/python -B manage.py test --verbosity 1` | **112 tests, OK**, 기존/신규 전체 suite |
| `.venv/bin/python -B manage.py check` | 문제 없음 |
| `.venv/bin/python -B manage.py makemigrations --check --dry-run` | No changes detected; 원본 적용 없음 |
| `.venv/bin/python -B manage.py load_curriculum_rules` | 17개 초안 정책 검증; DB 쓰기 없음 |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `npm test` | **34 passed, 0 failed** |
| `npm run typecheck` | exit0 |
| `npm run build` | Next15.5.27, 성공, 7/7 정적 페이지 및 동적 review 경로 |
| `npm audit` | **0 vulnerabilities** at execution |
| `git diff --check` | 통과 |
| Ruff E4/E7/E9/F, 동일 설정 HEAD 비교 | 기존29 → 현재21, **새 finding 없음**; 전체 기존 lint debt가 없다는 뜻은 아님 |
| 사본 DB 보존·무결성 | 기존 데이터/마이그레이션 이력·FK 통과 |
| PDF/DB 해시 | 기준값과 일치 |
| 실제 HTTP smoke | 아래14개 검사 통과; 합성계정/새 사설DB, 원본 DB 미사용 |
| 실제 로컬 OCR | 합성 영어 PNG 및 별도 합성 한국어 PNG 인식 성공 |

### 실제 HTTP smoke의 14개 검사

1. 회원가입
2. JWT 로그인
3. 인증된 프로필 조회
4. 프로필 수정
5. 수정값 read-back
6. 실제 합성 PDF multipart 업로드·inline 추출
7. raw·draft read-back 및 학수번호 유지
8. 미확정 성적표 분석 차단
9. 소유자 확정
10. 확정 상태 read-back
11. 초안 정책이 졸업완료로 승격되지 않음
12. 분석 조건의 PDF 페이지 근거 유지
13. 다른 사용자 ID의 업로드403
14. 실제 JWT refresh 계약

이 smoke는 서버를 localhost에서 잠깐 실행해 검증한 뒤 종료했다. 외부 배포가 아니다. UI 실제 브라우저 조작이나 익명화된 실학생 성적표 정확도 검증을 했다는 뜻도 아니다.

## 리뷰에서 발견해 수정한 문제

- 다른 탭·겹친 로그인·로그아웃 후 늦은 응답이 이전 계정 정보를 복원하던 문제: 공유 세션 세대·토큰 검사 및 read-back/캐시 수락 시점 보호, 대시보드 이전 요청 취소.
- 가입 학과명과 정책 selector 불일치: 명시적 컴퓨터공학과 선택, 기존 학부 값의 사용자 확인·수정. 학부를 임의로 컴공으로 추정하지 않음.
- `pending`을 비동기 처리중으로 안내하던 문제: 실제 평가 후 미충족 상태로 표시.
- null 학점/학기의 OCR 초안을 편집할 수 없던 문제: 초안 편집과 최종 확정 검증 분리.
- 지정과목의 존재만으로6학점을 충족하던 문제: 지정 쌍의 실제 학점과 과목 존재를 각각 검사. 기초교양6·글쓰기3·대학영어3·전공기초영어2·특성화3도 별도로 검사.
- 잘못된 정책의500/빈조건 완료 문제: 모델·import·평가 공유 검증, 정의된 오류 응답.
- 학점 합산 overflow: 유한 JSON 숫자 범위 검사, 재확정 필요 응답.
- 규칙/출처의 같은 버전 덮어쓰기: 모델 수준 불변성, 새 버전 행 요구.
- 상세 교과표 인쇄쪽수: PDF89→공-1,98→공-10,99→공-11. 번들은 `hongik-cs-2026-provided-draft-v2`이며 여전히 미검증 출처다.

독립 OCR 리뷰는 통과했다. 프론트·백엔드 수정 후 독립 재리뷰 결과는 아래 최종 승인 항목에 별도로 기록한다. 테스트 통과와 리뷰 승인을 혼동하지 않는다.

추가 재리뷰에서 확인한 같은 세션의 갱신 경쟁은, 세션 교체와 정상 토큰 회전을 구분하고 이미 갱신된 토큰을1회 재시도하도록 수정했다. 0학점 과목은 교양 필수영역이나 SW 모듈 슬롯을 충족하지 않지만 원본 수강 내역에는 유지한다. 두 반례 모두 evaluator/API 및 실제 대시보드 lifecycle 회귀 테스트로 검증했다. 출처 검증 플래그는 정확한 boolean True만 인정하고 복수 페이지 근거도 결과 JSON에 보존한다.

## Git 안전 범위

DB/성적표 이미지/환경파일/비밀번호·API키/캐시/가상환경/IDE 변경/제공 PDF 원본을 이번 commit 대상에서 제외한다. 변경된 settings 파일에는 기존 하드코딩 signing secret 대신 환경변수를 사용한다. 테스트의 명시적 합성 문자열은 실제 자격정보가 아니다.

원격 변경은 fetch와 ahead/behind 확인으로 검토하고, 선택한 파일만 stage한 뒤 staged diff·민감정보·DB 해시를 다시 검사한다. **force push는 사용하지 않는다.** 기존 이력에 이미 추적된 DB/media 및 과거 자격정보를 이번 변경만으로 Git 이력에서 제거했다고 주장하지 않는다. 그 정리는 별도 범위·승인이 필요하다.

## 남는 운영·문서 한계

- 제공본 `(안)`의 공식 최종본/정오표 여부, 인증 내규·논문/영어 증빙·휴복학/편입 경과조치의 개별 적용은 **검증 필요**다. 확정 졸업/인증 판정 기능으로 광고하지 않는다.
- 원본 DB에 추가 마이그레이션이 적용되지 않았으므로 **원본 DB를 그대로 사용하는 서버를 운영준비 완료로 보지 않는다**. 현재 완료 범위는 코드·테스트DB·허가된 사본 검증이다.
- Celery worker/broker의 실제 상시 운영과 외부 배포는 검증/수행하지 않았다. 로컬은 명시적 inline 선택이 가능하다.
- Vision은 macOS/Swift 선택형 공급자다. 다른 플랫폼은 공급자 설정 또는 수동입력이 필요하다. 실제 학생 성적표의 OCR·레이아웃 정확도는 별도 동의된 익명 샘플로 검증해야 한다.
- 레거시 개별 분석 endpoint는 호환용이며 미검증 기존 기준을 사용할 수 있다. 새 대시보드는 보수적 통합 report endpoint를 사용한다.
- 위사항은 미확인 내용을 성공으로 간주한 것이 아니라 명시적으로 남겨 둔 범위다.

## 최종 승인

프론트·백엔드 독립 재리뷰 모두 **passed=true**, 보안/논리 blocker 없음으로 승인됐다. 독립 백엔드 전체112개 테스트와 프론트34개 테스트·타입 검사도 통과했다. 선택형 OCR 어댑터의 별도 독립 리뷰도 통과했다. 최종 승인 범위는 코드·격리 검증이며 위에 명시한 원본 DB 미적용·공식 기준 검증·운영 배포 한계는 그대로다.

commit 직전 선택한 변경 파일과 staged diff, 민감정보 제외, 원격 브랜치·원본 DB 해시를 다시 검사한다. 실제 커밋 해시와 push 결과는 Git 기록 및 사용자 완료 보고에서 확인한다.
