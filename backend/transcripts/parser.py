"""Explicit, delimited headers only. Preserve unknown lines; infer no policy."""
import re
from common.course_schema import CourseSchemaError, normalize_course, normalize_course_document

LABELS = {
    'code': 'code', '학수번호': 'code', '학수코드': 'code', '과목코드': 'code',
    'name': 'name', '교과목명': 'name', '과목명': 'name',
    'credit': 'credit', '학점': 'credit', 'grade': 'grade', '성적': 'grade', '등급': 'grade',
    'semester': 'semester', '학기': 'semester',
    'type': 'type', '이수구분': 'type', '구분': 'type',
    'major_field': 'major_field', '영역': 'major_field', '전공영역': 'major_field',
}


def split_columns(line):
    if '|' in line:
        return [cell.strip() for cell in line.split('|')]
    if '\t' in line:
        return [cell.strip() for cell in line.split('\t')]
    return re.split(r'\s{2,}', line.strip())


def parse_course_pages(raw):
    courses, unparsed = [], []
    warnings = list(raw.get('warnings', []))
    incomplete = bool(warnings)
    for page in raw.get('pages', []):
        columns = None
        for number, line in enumerate(page.get('text', '').splitlines(), 1):
            if not line.strip():
                continue
            cells = split_columns(line)
            header = [LABELS.get(re.sub(r'\s+', '', cell).lower()) for cell in cells]
            if (all(header) and len(set(header)) == len(header)
                    and {'name', 'credit'}.issubset(header)):
                columns = header
                continue
            reason = 'No explicit course header or column count mismatch.'
            if columns and len(cells) == len(columns):
                try:
                    course = normalize_course(dict(zip(columns, cells)))
                    course['source_page'] = page['page_number']
                    course['source_line'] = number
                    courses.append(course)
                    try:
                        normalize_course(course, for_confirmation=True)
                    except CourseSchemaError:
                        incomplete = True
                        warnings.append({'code': 'incomplete_course', 'page_number': page['page_number'],
                                         'line_number': number, 'message': 'Missing course values; manual correction required.'})
                    continue
                except CourseSchemaError:
                    reason = 'Invalid course values; retained for manual correction.'
            incomplete = True
            unparsed.append({'page_number': page['page_number'], 'line_number': number,
                             'text': line, 'reason': reason})
    if unparsed:
        warnings.append({'code': 'unparsed_lines', 'message': 'Some lines were not safely parsed; review the raw text.'})
    if not courses:
        incomplete = True
        warnings.append({'code': 'no_courses', 'message': 'No courses safely recognized; enter them manually.'})
    return normalize_course_document({'schema_version': 1, 'courses': courses, 'needs_review': True,
                                     'incomplete': incomplete, 'warnings': warnings, 'unparsed_lines': unparsed})
