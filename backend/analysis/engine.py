"""Evidence-bearing, conservative rule evaluator; no university numbers here."""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
from math import isfinite
import re
import unicodedata

from common.course_schema import CourseSchemaError, normalize_course_document
from django.core.exceptions import ValidationError
from .policy import validate_policy_data

PASS_GRADES = {'A+', 'A0', 'A', 'B+', 'B0', 'B', 'C+', 'C0', 'C', 'D+', 'D0', 'D', 'P', 'PASS'}


def name_key(value):
    return re.sub(r'[\s·ㆍ()（）._-]', '', unicodedata.normalize('NFKC', value or '')).casefold()


def evaluate_rules(policy, document, *, course_catalog=None):
    if not isinstance(policy, dict):
        raise ValidationError('규칙 문서는 객체여야 합니다.')
    validate_policy_data(policy.get('data'))
    document = normalize_course_document(document, for_confirmation=True)
    if course_catalog is not None:
        from .course_identity import resolve_document, recognition_links
        document = resolve_document(document, course_catalog)
    rules = policy['data']['criteria']
    catalog = policy['data']['catalog']
    by_code = {row['code']: row for row in catalog if row.get('code')}
    relations = {r['from_code']:r for r in policy['data'].get('course_relations', [])
                 if r.get('official_verified') is True and policy.get('source_verified') is True}
    records, warnings = [], []
    if not rules:
        warnings.append('판정 규칙이 없습니다. 검증 필요.')
    for course in document['courses']:
        row = deepcopy(course)
        for computed in ('course_relation', 'retake_targets', 'classification_provisional'):
            row.pop(computed, None)
        relation = relations.get(row.get('code')) if course_catalog is None else None
        canonical = relation['to_code'] if relation and relation['kind']=='same_course' else row.get('code')
        matches = [by_code[canonical]] if canonical in by_code else []
        if relation:
            row['course_relation'] = deepcopy(relation)
        # Replacement relations keep separate identities and never silently satisfy
        # a mandatory course. Such recognition must be an explicit sourced rule.
        # Unknown codes never acquire the identity of a similarly named course.
        if not row.get('code'):
            matches = []  # Names/aliases are hints, never an identity authority.
        links = None
        if course_catalog is not None:
            links = recognition_links(row['identification'], course_catalog, policy)
            matches = [by_code[c] for c in links['codes'] if c in by_code] if links else ([by_code[row['code']]] if row.get('code') in by_code and not row['identification']['candidates'] else [])
            row['classification_provisional'] = links is None
            if row['identification']['issues']:
                warnings.append(f"과목 이력 확인 필요: {row['name']} — " + ' / '.join(row['identification']['issues']))
        matched = matches[0] if len(matches) == 1 else None
        row['roles'] = deepcopy(matched.get('roles', [])) if matched else []
        row['area'] = matched.get('area') if matched else None
        row['sw_level'] = matched.get('sw_level') if matched else None
        row['identity'] = matched.get('code') if matched else (row.get('code') or name_key(row['name']))
        row['requirement_codes'] = [matched['code']] if matched else []
        row['substitutions'] = {}
        if course_catalog is not None and not links:
            row['requirement_codes'] = []
        if links:
            row['identity'] = links['identity']
            row['requirement_codes'] = links['codes']
            row['substitutions'] = links['replacements']
            row['retake_targets'] = links['retake_targets']
        row['catalog_matched'] = matched is not None
        if not matched:
            warnings.append(f"분류 근거 확인 필요: {row['name']} ({row.get('code') or '코드 없음'})")
        records.append(row)
    names = defaultdict(list)
    for row in records:
        names[name_key(row['name'])].append(row)
    replacements = {frozenset((r['from_code'],r['to_code'])) for r in relations.values() if r['kind']=='replacement'}
    if course_catalog is not None:
        from .course_identity import verified_relations
        version_map = {v['id']:v for v in course_catalog['versions']}
        replacements.update(frozenset((version_map[r['source']]['course_id'], version_map[r['target']]['course_id']))
                            for r in verified_relations(course_catalog) if r['kind']=='replacement')
    for group in names.values():
        codes = {row['identity'] for row in group}
        if len(codes)>1 and frozenset(codes) not in replacements:
            for row in group:
                row['identity_conflict'] = True
    if course_catalog is not None:
        for row in records:
            if any(other['identification'].get('version_id') in row.get('retake_targets', []) for other in records if other is not row):
                row['retake_candidate'] = True
                for other in records:
                    if other['identification'].get('version_id') in row.get('retake_targets', []):
                        other['retake_candidate'] = True
    # Explicit retake permission is not an instruction to count both attempts.
    retake_conflicts = set()
    for row in records:
        if row.get('credit_decision') == 'exclude' or row['grade'].strip().upper() in {'F','NP'}:
            continue
        for other in records:
            if (other is not row and other.get('credit_decision') != 'exclude' and other['grade'].strip().upper() not in {'F','NP'}
                    and other.get('identification', {}).get('version_id') in row.get('retake_targets', [])):
                retake_conflicts.update((row['identity'], other['identity']))
    counts = Counter(row['identity'] for row in records if row.get('credit_decision') != 'exclude' and row['grade'].strip().upper() not in {'F','NP'})
    duplicate = {key for key, count in counts.items() if count > 1} | retake_conflicts
    if course_catalog is not None:
        by_observed_code = defaultdict(list)
        for row in records:
            if row.get('code') and row.get('credit_decision') != 'exclude' and row['grade'].strip().upper() not in {'F','NP'}:
                by_observed_code[row['code']].append(row)
        for group in by_observed_code.values():
            if len(group) > 1 and any(r['identification']['status'] != 'matched' for r in group):
                duplicate.update(r['identity'] for r in group)
    eligible = []
    recognition_review = document.get('incomplete') is True or (course_catalog is not None and any(
        r['identification']['status'] != 'matched' for r in records))
    if recognition_review:
        warnings.append('OCR 누락·불확실 항목이 표시된 자료입니다. 원본 전체와 대조가 필요합니다.')
    for row in records:
        grade = row['grade'].strip().upper()
        row['credit_counted'] = False
        if row.get('credit_decision') == 'exclude':
            row['recognition_reason'] = '사용자가 원본 대조 후 인정 제외'
            continue
        if grade in {'F', 'NP'}:
            row['recognition_reason'] = '미취득 성적'
            continue
        if (row['identity'] in duplicate or
                ((row.get('retake') or row.get('semester_retake') or row.get('retake_candidate') or row.get('capture_conflict') or row.get('identity_conflict'))
                 and row.get('credit_decision') != 'include')):
            recognition_review = True
            warnings.append(f"중복·재수강 인정 검증 필요: {row['name']}")
            continue
        if grade == 'F':
            continue
        if grade not in PASS_GRADES:
            recognition_review = True
            warnings.append(f"성적 인정 검증 필요: {row['name']} ({row['grade']})")
            continue
        row['credit_counted'] = True
        row['recognition_reason'] = '사용자 확인 기반 계산' if row.get('credit_decision') == 'include' else '취득 기록'
        eligible.append(row)

    def selected(roles):
        if 'total' in roles:
            return eligible
        return [row for row in eligible if set(row['roles']).intersection(roles)]

    def credits(rows):
        value = float(sum((Decimal(str(row['credit'])) for row in rows), Decimal(0)))
        if not isfinite(value):
            raise CourseSchemaError('인정학점 합계가 유한한 JSON 숫자 범위를 벗어났습니다.')
        return value

    # Prove the aggregate is representable before any cap/group arithmetic.
    credits(eligible)

    results = []
    for rule in rules:
        result = {'id':rule['id'], 'label':rule.get('label', rule['id']), 'source':deepcopy(rule.get('source', {}))}
        if 'additional_sources' in rule:
            result['additional_sources'] = deepcopy(rule['additional_sources'])
        kind = rule.get('kind')
        met = False
        missing = []
        affected = False
        if kind == 'credits':
            value = credits(selected(rule['roles']))
            if 'cap_role' in rule:
                excess = max(0, credits(selected([rule['cap_role']])) - rule['cap'])
                value = max(0, value - excess)
            result.update(completed=value, required=rule['minimum'], remaining=max(0, round(rule['minimum']-value, 6)))
            met = value >= rule['minimum']
            affected = (rule['roles'] != ['total'] or 'cap_role' in rule) and any(not r['catalog_matched'] for r in eligible)
        elif kind == 'course_groups':
            def codes_for(row):
                return set(row['requirement_codes']) | set(row['substitutions'].get(rule['id'], []))
            identities = {code for row in eligible if row['credit'] > 0 for code in codes_for(row)}
            completed = [group for group in rule['groups'] if set(group).issubset(identities)]
            complete_groups = len(completed)
            needed = rule.get('minimum_count', len(rule['groups']))
            met = complete_groups >= needed
            if 'minimum_credit' in rule:
                # Only the selected complete groups fund this obligation. Other
                # MSC/general credits and multiple partial alternatives cannot.
                completed.sort(key=lambda group: credits([row for row in eligible if codes_for(row).intersection(group)]), reverse=True)
                chosen = {code for group in completed[:needed] for code in group}
                value = credits([row for row in eligible if codes_for(row).intersection(chosen)])
                minimum = rule['minimum_credit']
                met = met and value >= minimum
                result.update(completed_credit=value, required_credit=minimum, remaining_credit=max(0, minimum-value))
            missing = [catalog_item['name'] for group in rule['groups'] if not set(group).issubset(identities) for code in group if code not in identities for catalog_item in catalog if catalog_item.get('code') == code]
            result.update(completed=complete_groups, required=needed, remaining=max(0, needed-complete_groups))
        elif kind == 'areas':
            covered = {row['area'] for row in eligible if row['area'] and row['credit'] > 0}
            mandatory = set(rule.get('mandatory', []))
            missing = sorted(mandatory - covered)
            met = len(covered) >= rule['minimum_count'] and not missing
            result.update(completed=len(covered), required=rule['minimum_count'], remaining=max(0,rule['minimum_count']-len(covered)), covered=sorted(covered))
        elif kind == 'sw_modules':
            candidates = sorted([row for row in eligible if row['sw_level'] and row['credit'] > 0], key=lambda row:row['sw_level'], reverse=True)
            slots = [3,2,1]
            used = []
            for slot in slots:
                match = next((row for row in candidates if row['sw_level'] >= slot and row['identity'] not in used), None)
                if match:
                    used.append(match['identity'])
            value = credits(candidates)
            met = len(used) == 3 and value >= rule['minimum']
            result.update(completed=value, required=rule['minimum'], remaining=max(0,rule['minimum']-value), slots_filled=len(used))
            if len(used) != 3:
                missing = ['서로 다른 과목으로 심화·기초·소양 모듈 충족 필요']
        else:
            result['status'] = 'needs_verification'
            result['reason'] = rule.get('reason', '문서로 확정할 수 없는 규칙입니다.')
            results.append(result)
            continue
        result['status'] = 'met' if met else 'not_met'
        if kind in {'course_groups', 'areas', 'sw_modules'}:
            affected = any(not row['catalog_matched'] for row in eligible)
        if recognition_review or (affected and not met):
            result['status'] = 'needs_verification'
        if missing:
            result['missing'] = list(dict.fromkeys(missing))
        results.append(result)
    if any(r.get('credit_decision') == 'include' and (r.get('retake') or r.get('semester_retake') or r.get('retake_candidate') or r.get('identity_conflict')) for r in records):
        warnings.append('재수강·동일과목 인정 기록은 사용자 확인을 반영한 잠정 계산입니다. 학교의 최종 인정 정책 확인 필요.')
    if policy.get('source_verified') is not True:
        warnings.append('제공 PDF 파일명/메타데이터에 (안)이 있습니다. 공식 최종본·정오표 검증 필요.')
    needs_review = bool(warnings) or any(row['status']=='needs_verification' for row in results)
    overall = 'needs_verification' if needs_review else ('pending' if any(row['status']=='not_met' for row in results) else 'complete')
    semesters = defaultdict(list)
    for row in records:
        semesters[row['semester']].append(row)
    return {'status':overall, 'criteria':results, 'courses':records, 'by_semester':dict(semesters), 'warnings':list(dict.fromkeys(warnings))}
