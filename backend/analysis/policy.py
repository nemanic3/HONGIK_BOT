"""Read-only, versioned rules from the provided PDF. Unknown selections fail closed."""
from copy import deepcopy
from functools import lru_cache
import json
from math import isfinite
from pathlib import Path

from django.core.exceptions import ValidationError

SUPPORTED_TRACKS = {'accredited', 'non_accredited'}
MAJOR_ALIASES = {'컴퓨터공학과', '컴퓨터공학전공', '컴퓨터·데이터공학부 컴퓨터공학전공', '정보·컴퓨터공학부 컴퓨터공학전공'}


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{field}: 비어 있지 않은 문자열이 필요합니다.')


def _strings(value, field, *, nonempty=False, unique=True):
    if not isinstance(value, list) or (nonempty and not value):
        raise ValidationError(f'{field}: 문자열 배열이 필요합니다.')
    for item in value:
        _text(item, field)
    if unique and len(set(value)) != len(value):
        raise ValidationError(f'{field}: 중복 식별자는 허용하지 않습니다.')


def _number(value, field):
    try:
        valid = type(value) in (int, float) and isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValidationError(f'{field}: 음수가 아닌 유한한 JSON 숫자가 필요합니다.')


def _count(value, field):
    if type(value) is not int or value < 1:
        raise ValidationError(f'{field}: 양의 정수가 필요합니다.')


def _source(value):
    if not isinstance(value, dict):
        raise ValidationError('source: PDF·인쇄 페이지 객체가 필요합니다.')
    _count(value.get('pdf_page'), 'pdf_page')
    _text(value.get('printed_page'), 'printed_page')


def _sources(row):
    _source(row.get('source'))
    if 'additional_sources' in row:
        if not isinstance(row['additional_sources'], list):
            raise ValidationError('additional_sources: 페이지 근거 배열이 필요합니다.')
        for source in row['additional_sources']:
            _source(source)


def validate_policy_data(data):
    """One strict contract for model clean, imports and live evaluation."""
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValidationError('지원하는 규칙 문서가 아닙니다.')
    rules, catalog = data.get('criteria'), data.get('catalog')
    if not isinstance(rules, list) or not rules or not isinstance(catalog, list):
        raise ValidationError('비어 있지 않은 규칙 배열과 과목 배열이 필요합니다.')
    codes = set()
    for row in catalog:
        if not isinstance(row, dict):
            raise ValidationError('과목은 객체여야 합니다.')
        _text(row.get('code'), 'catalog.code')
        _text(row.get('name'), 'catalog.name')
        if row['code'] in codes:
            raise ValidationError('중복 과목 식별자는 허용하지 않습니다.')
        codes.add(row['code'])
        _sources(row)
        _strings(row.get('roles', []), 'catalog.roles')
        _strings(row.get('aliases', []), 'catalog.aliases', unique=False)
        if row.get('area') is not None:
            _text(row['area'], 'catalog.area')
        level = row.get('sw_level')
        if level is not None and (type(level) is not int or level not in (1, 2, 3)):
            raise ValidationError('sw_level: 1·2·3 또는 null이어야 합니다.')
    relations = data.get('course_relations', [])
    if not isinstance(relations, list):
        raise ValidationError('course_relations는 배열이어야 합니다.')
    linked = set()
    for relation in relations:
        if not isinstance(relation, dict) or relation.get('kind') not in ('same_course', 'replacement'):
            raise ValidationError('동일과목과 대체과목 관계를 구분해야 합니다.')
        if 'official_verified' in relation and type(relation['official_verified']) is not bool:
            raise ValidationError('official_verified는 명시적 불리언이어야 합니다.')
        _sources(relation)
        _text(relation.get('source_document'), 'source_document')
        _text(relation.get('from_code'), 'from_code')
        _text(relation.get('to_code'), 'to_code')
        if relation['from_code'] == relation['to_code'] or relation['to_code'] not in codes or relation['from_code'] in linked:
            raise ValidationError('과목 관계가 중복되거나 대상이 불명확합니다.')
        linked.add(relation['from_code'])
    if any(r['to_code'] in linked for r in relations):
        raise ValidationError('연쇄 관계는 최종 동일과목으로 정규화해야 합니다.')
    ids = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValidationError('규칙은 객체여야 합니다.')
        _text(rule.get('id'), 'rule.id')
        _text(rule.get('kind'), 'rule.kind')
        if rule['id'] in ids:
            raise ValidationError('중복 규칙 식별자는 허용하지 않습니다.')
        ids.add(rule['id'])
        _sources(rule)
        if 'label' in rule:
            _text(rule['label'], 'rule.label')
        for field in ('minimum', 'minimum_credit', 'cap'):
            if field in rule:
                _number(rule[field], field)
        kind = rule['kind']
        if kind == 'credits':
            _number(rule.get('minimum'), 'minimum')
            _strings(rule.get('roles'), 'roles', nonempty=True)
            if 'cap_role' in rule or 'cap' in rule:
                _text(rule.get('cap_role'), 'cap_role')
                _number(rule.get('cap'), 'cap')
        elif kind == 'course_groups':
            groups = rule.get('groups')
            if not isinstance(groups, list) or not groups:
                raise ValidationError('groups: 비어 있지 않은 과목군 배열이 필요합니다.')
            group_ids = set()
            for group in groups:
                _strings(group, 'groups', nonempty=True)
                identity = frozenset(group)
                if not identity.issubset(codes) or identity in group_ids:
                    raise ValidationError('과목군에 미등록·중복 식별자가 있습니다.')
                group_ids.add(identity)
            needed = rule.get('minimum_count', len(groups))
            _count(needed, 'minimum_count')
            if needed > len(groups):
                raise ValidationError('minimum_count가 과목군 수를 초과합니다.')
        elif kind == 'areas':
            _count(rule.get('minimum_count'), 'minimum_count')
            _strings(rule.get('mandatory', []), 'mandatory')
        elif kind == 'sw_modules':
            _number(rule.get('minimum'), 'minimum')
        # Unknown kinds remain review-only, never successful vacuous rules.


@lru_cache(maxsize=1)
def bundle():
    return json.loads((Path(__file__).parent/'data/hongik_cs_2026.json').read_text(encoding='utf-8'))


def select_policy(major, admission_year, track):
    if major not in MAJOR_ALIASES or type(admission_year) is not int or track not in SUPPORTED_TRACKS:
        return None
    matches = [row for row in bundle()['policies'] if row['accreditation_track']==track and row['admission_year_from'] <= admission_year <= row['admission_year_to']]
    return deepcopy(matches[0]) if len(matches)==1 else None


def policy_for_user(user):
    from .models import RequirementRuleSet
    if user.major not in MAJOR_ALIASES or not user.admission_year or user.accreditation_track not in SUPPORTED_TRACKS:
        return None
    candidates = list(RequirementRuleSet.objects.filter(
        major='컴퓨터공학과', campus='서울',
        admission_year_from__lte=user.admission_year, admission_year_to__gte=user.admission_year,
        accreditation_track=user.accreditation_track, curriculum_year=2026,
    ).order_by('pk')[:2])
    if len(candidates)>1:
        return None # Ambiguous overlaps/versions require an explicit resolution.
    if candidates:
        fields = ['major','campus','admission_year_from','admission_year_to','curriculum_year','accreditation_track','version','source_document','source_sha256','source_verified','data']
        return {field:deepcopy(getattr(candidates[0],field)) for field in fields}
    return select_policy(user.major, user.admission_year, user.accreditation_track)
