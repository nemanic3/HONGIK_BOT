# team4-frontend
HICC 2025-1 Team4 프론트엔드 레포지토리입니다.

## Local verification

```sh
npm install
npm test
npm run typecheck
npm run build
```

Node 26 native type stripping runs the pure contract tests; TSX regressions use the installed TypeScript compiler and React renderer with controlled lifecycle/platform seams, without another test dependency. Next 15.5.27 / React 19.1.0 are used. Security-audited overrides pin PostCSS 8.5.23 and Sharp 0.35.5 without a Next major-version upgrade. Tests exercise local contract fixtures, not a live OCR/backend service.

## API configuration and reconciliation

- `NEXT_PUBLIC_API_BASE_URL` is the only API base variable (default `http://127.0.0.1:8000`).
- `NEXT_PUBLIC_AUTH_REFRESH_PATH` defaults to the verified backend route `/api/users/refresh/`; override only with an actual same-origin relative endpoint. Refresh expects POST `{ "refresh": "…" }` → `{ "access": "…", "refresh"?: "…" }`, shares concurrent refreshes, and retries once.
- Login: POST `/api/users/login/` → access/refresh, then authenticated GET `/api/users/me/` → numeric `id` and profile. A failed profile lookup fails the login closed; no JWT ID inference or fallback user exists.
- Signup: POST `/api/users/signup/` explicitly includes `major`, `admission_year` and `accreditation_track` (`accredited` / `non_accredited`) as well as existing fields. The offered major is the selector-supported canonical `컴퓨터공학과`, not an ambiguous umbrella 학부.
- Profile editor uses the existing PATCH `/api/users/update-profile/` with `{ major, admission_year, accreditation_track }`, followed by GET `/api/users/me/` read-back of all three fields. Supported exact majors are `컴퓨터공학과`, `컴퓨터공학전공`, `컴퓨터·데이터공학부 컴퓨터공학전공`, and `정보·컴퓨터공학부 컴퓨터공학전공`. Ambiguous legacy majors start unselected and require an explicit user choice; they are never automatically mapped to computer engineering.
- Upload: POST `/api/transcripts/<authenticated me.id>/` multipart repeated `files`, combined maximum 5MiB. A returned `transcript_id` is required. HTTP 503 with a valid `transcript_id` also opens ID-based review for manual correction.
- Review: GET `/api/transcripts/detail/<id>/`. The supplied contract fields are `id`, `status`, `error_message`, `source`, `ocr_raw_data`, `document`, `confirmed_at`. `processing` / `pending` / `queued` poll for at most 120 seconds; request timeout is 30 seconds. Error/timeout can enter manual review **only after authenticated detail was obtained**.
- Confirm: POST `/api/transcripts/confirm/<id>/` with the full document, then GET detail read-back requiring matching ID and `confirmed_at`. Document header is `{ "schema_version": 1, "courses": [...] }`. Draft rows retain string `code`, `name`, `type`, `grade` plus nullable `semester` and nullable numeric `credit`; null values render as editable blanks. Confirm validation separately requires nonblank `name`, `type`, `grade`, `semester` and finite nonnegative numeric `credit`. String codes preserve leading zeros. Extra document/course metadata (including `aliases`, `retake`, `academic_year`, `term`, `major_field`, confidence and source details) is retained in the full payload; arbitrary OCR text is not guessed into courses. New manual rows and cleared credit/semester cells remain unknown (`null`), never fabricated zero credits.
- Dashboard: one analysis endpoint, GET `/api/analysis/report/?transcript_id=<id>` (or without query for latest). The returned report feeds all three existing cards. Report `pending` means calculation is complete with unmet criteria, not asynchronous processing (unlike transcript OCR polling statuses). Requirements, warnings, missing-item strings, semester groups and page references come only from this report. Unverified policy sources force a visible `검증 필요`, even when an individual numeric threshold is met. No graduation thresholds are hardcoded.
- Logout clears token/profile/transcript selections and legacy identity keys, retaining a unique `authSessionGeneration` tombstone to invalidate pending login attempts across tabs. Response acceptance and `/me/` caching check persisted session generation; legitimate same-session token rotation does not terminate outstanding reads. Token snapshots govern refresh ownership and whether a failed retry may log out; stale failures cannot logout a newer account. Overlapping logins only let the current attempt persist credentials. Dashboard storage identity changes abort old reads, clear old profile/report/editor state, discard the previous URL transcript selection, and reload a new nonempty session. Components cancel requests, polls and timers on unmount. There is no implemented delete-transcript or contact endpoint; the sidebar labels those unavailable rather than wiring invalid actions.

Homepage source and original card/modal CSS are retained. The upload CSS's invalid global-only module selectors were scoped to a header wrapper so production compilation succeeds without styling dashboard card headers globally.
