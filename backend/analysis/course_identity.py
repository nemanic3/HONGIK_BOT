"""Server-owned, semester-specific identification. Never rewrite observed fields."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
import unicodedata


def name_key(value):
    return re.sub(r'[\s·ㆍ()（）._-]', '', unicodedata.normalize('NFKC', value or '')).casefold()


def actual_term(row):
    match = re.fullmatch(r'(\d{4})-(1|2|summer|winter)', str(row.get('semester') or ''))
    if not match:
        return None
    year, term = int(match[1]), match[2]
    if year < 1900:
        return None
    if row.get('academic_year') not in (None, year) or row.get('term') not in (None, '', term):
        return None
    return year, term


def catalog_snapshot(major, campus='서울'):
    from .models import CourseVersion, CourseRelation
    from .policy import MAJOR_ALIASES
    if major in MAJOR_ALIASES:
        major = '컴퓨터공학과'
    versions = list(CourseVersion.objects.filter(major=major, campus=campus).select_related('evidence'))
    ids = {v.pk for v in versions}
    def evidence(e):
        return {'document':e.document, 'sha256':e.sha256, 'pdf_page':e.pdf_page,
                'printed_page':e.printed_page, 'statement':e.statement,
                'verified':bool(e.official_verified and e.verified_at and e.verified_by)}
    rows = [{'id':v.pk, 'course_id':str(v.course_id), 'year':v.academic_year, 'term':v.term,
             'code':v.code, 'name':v.name, 'credit':float(v.credit) if v.credit is not None else None,
             'type':v.classification, 'evidence':evidence(v.evidence)} for v in versions]
    relations = [{'source':r.source_id, 'target':r.target_id, 'kind':r.kind,
                  'policy_version':r.policy_version, 'criterion_id':r.criterion_id,
                  'evidence':evidence(r.evidence)} for r in CourseRelation.objects.filter(
                      source_id__in=ids, target_id__in=ids).select_related('evidence')]
    return {'versions':rows, 'relations':relations}


def resolve_document(document, snapshot):
    if document is None:
        return None
    result = deepcopy(document)
    versions = snapshot['versions']
    for row in result.get('courses', []):
        # Client metadata is not evidence, including metadata from an earlier edit.
        row.pop('identification', None)
        issues = []
        term = actual_term(row)
        code = row.get('code')
        if not code:
            issues.append('학수번호 확인 필요')
        if not term:
            issues.append('실제 수강연도·학기 확인 필요 (예: 2021-1)')
        candidates = [v for v in versions if code and v['code']==code and term and (v['year'],v['term'])==term]
        matched = candidates[0] if len(candidates)==1 else None
        if not matched:
            issues.append('해당 학수번호·수강학기의 공식 변경 이력 미확인' if not candidates else '동일 학수번호·학기에 여러 과목 후보 존재')
        else:
            if not matched['evidence']['verified']:
                issues.append('과목 자료의 공식 출처 확인 필요')
            if name_key(row.get('name')) != name_key(matched['name']):
                issues.append('과목명 불일치')
            try:
                credit_matches = matched['credit'] is not None and Decimal(str(row.get('credit'))) == Decimal(str(matched['credit']))
            except (InvalidOperation, ValueError):
                credit_matches = False
            if not credit_matches:
                issues.append('학점 불일치 또는 기준 학점 미확인')
            if not matched['type'] or row.get('type') != matched['type']:
                issues.append('이수구분 불일치 또는 기준 미확인')
        row['identification'] = {'status':'needs_review' if issues else 'matched', 'issues':issues,
                                  'course_id':matched['course_id'] if matched and not issues else None,
                                  'version_id':matched['id'] if matched and not issues else None,
                                  'candidates':deepcopy(candidates)}
    return result


def identify_for_user(document, user):
    return resolve_document(document, catalog_snapshot(user.major))


def verified_relations(snapshot):
    versions = {v['id']:v for v in snapshot['versions']}
    return [r for r in snapshot['relations'] if r['evidence']['verified']
            and versions[r['source']]['evidence']['verified'] and versions[r['target']]['evidence']['verified']]


def recognition_links(identification, snapshot, policy):
    """Separate duplicate-credit identity, requirement targets, retake candidates."""
    start = identification.get('version_id')
    if start is None:
        return None
    versions = {v['id']:v for v in snapshot['versions']}
    relations = verified_relations(snapshot)
    # Same identity is safe only for unchanged attributes (model invariant).
    component = {start}
    while True:
        expanded = component | {v['id'] for v in versions.values() if v['evidence']['verified'] and any(v['course_id']==versions[i]['course_id'] for i in component)}
        for r in relations:
            if r['kind']=='same_course' and ({r['source'],r['target']} & component):
                expanded.update((r['source'],r['target']))
        if expanded == component:
            break
        component = expanded
    target_year = policy.get('curriculum_year')
    codes = {versions[i]['code'] for i in component if versions[i]['year']==target_year}
    replacements = {}
    retakes = []
    for r in relations:
        if r['source'] in component and r['kind']=='replacement' and r['policy_version']==policy.get('version') and versions[r['target']]['year']==target_year:
            replacements.setdefault(r['criterion_id'], []).append(versions[r['target']]['code'])
        if r['kind']=='retake' and r['source'] in component:
            retakes.append(r['target'])
    return {'identity':min(versions[i]['course_id'] for i in component), 'codes':sorted(codes),
            'replacements':replacements, 'retake_targets':retakes}
