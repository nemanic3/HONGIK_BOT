"""Explicit, delimited headers only. Preserve unknown lines; infer no policy."""
import re
from common.course_schema import CourseSchemaError, normalize_course, normalize_course_document

LABELS = {
    'code': 'code', '학수번호': 'code', '학수코드': 'code', '과목코드': 'code',
    'name': 'name', '교과목명': 'name', '과목명': 'name',
    'credit': 'credit', '학점': 'credit', 'grade': 'grade', '성적': 'grade', '등급': 'grade',
    'semester': 'semester', '학기': 'semester',
    'type': 'type', '이수구분': 'type', '구분': 'type',
    '영문과목명': 'english_name', '재수강': 'retake',
    'major_field': 'major_field', '영역': 'major_field', '전공영역': 'major_field',
}


def split_columns(line):
    if '|' in line:
        return [cell.strip() for cell in line.split('|')]
    if '\t' in line:
        return [cell.strip() for cell in line.split('\t')]
    return re.split(r'\s{2,}', line.strip())


def spatial_lines(page):
    """Rebuild cells from their positions, retaining the original OCR separately.

    Only explicit single-table headers are accepted. Missing cells stay empty;
    side-by-side tables are left for review instead of mixing their courses.
    """
    boxes = page.get('observations', [])
    if not boxes:
        return page.get('text', '').splitlines()
    rows = []
    for box in sorted(boxes, key=lambda b: b['y'] + b['height'] / 2):
        center = box['y'] + box['height'] / 2
        if rows and abs(center - rows[-1][0]) < min(box['height'], rows[-1][1]) * .55:
            rows[-1][2].append(box)
        else:
            rows.append([center, box['height'], [box]])
    output, anchors = [], None
    for _, _, row in rows:
        row.sort(key=lambda b: b['x'])
        labels = [LABELS.get(re.sub(r'\s+', '', b['text']).lower()) for b in row]
        if 'code' in labels and 'name' in labels and 'credit' in labels:
            if None in labels or len(set(labels)) != len(labels):
                anchors = None
            else:
                anchors = [b['x'] + b['width'] / 2 for b in row]
                labels_for_table = labels
                output.append('|'.join(b['text'] for b in row))
                continue
        if anchors and re.fullmatch(r'\d{6}', row[0]['text'].strip()):
            cells = [box['text'].strip() for box in row]
            # Blank retake cells have no OCR box. Other missing/merged cells
            # must remain unparsed rather than shift into neighboring fields.
            if len(cells) == len(anchors) - 1 and labels_for_table[-1] == 'retake':
                cells.append('')
            if len(cells) != len(anchors):
                output.append(' '.join(cells))
                continue
            values = dict(zip(labels_for_table, cells))
            if (not re.fullmatch(r'\d{6}', values.get('code', ''))
                    or not re.fullmatch(r'\d+(?:\.\d+)?', values.get('credit', ''))
                    or not re.fullmatch(r'(?:[ABCD][+0O-]?|[FP]|NP)', values.get('grade', ''))):
                output.append(' '.join(cells))
                continue
            output.append('|'.join(cells))
        else:
            output.append(' '.join(b['text'] for b in row))
    return output


def parse_course_pages(raw):
    from .spatial import extract, merge_captures, restore_headers
    courses, unparsed = [], []
    warnings = list(raw.get('warnings', []))
    incomplete = bool(warnings)
    previous = None
    for original in raw.get('pages', []):
        page = restore_headers(original, previous)
        spatial = extract(page)
        if page.get('observations'): previous = page
        if spatial is not None:
            rows, issues = spatial
            courses.extend(normalize_course(row) for row in rows)
            warnings.extend(issues)
            incomplete = incomplete or bool(issues) or any(row.get('review_reasons') for row in rows)
            continue
        columns = None
        semester = None
        for number, line in enumerate(spatial_lines(page), 1):
            if not line.strip():
                continue
            term = re.fullmatch(r'(\d{4})학년도\s+\d학년\s+([12])학기', line.strip())
            if term:
                semester = f'{term[1]}-{term[2]}'
                columns = None
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
                    values = dict(zip(columns, cells))
                    if 'retake' in values:
                        if values['retake'] not in ('', '재수강'):
                            raise CourseSchemaError('Unknown retake marker')
                        values['retake'] = values['retake'] == '재수강'
                    if semester and not values.get('semester'):
                        values['semester'] = semester
                    course = normalize_course(values)
                    course['sources'] = [{'file_number':page.get('file_number',1),'page_number':page['page_number']}]
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
    courses = merge_captures(courses)
    incomplete = incomplete or any(row.get('review_reasons') for row in courses)
    if unparsed:
        warnings.append({'code': 'unparsed_lines', 'message': 'Some lines were not safely parsed; review the raw text.'})
    if not courses:
        incomplete = True
        warnings.append({'code': 'no_courses', 'message': 'No courses safely recognized; enter them manually.'})
    return normalize_course_document({'schema_version': 1, 'courses': courses, 'needs_review': True,
                                     'incomplete': incomplete, 'warnings': warnings, 'unparsed_lines': unparsed})
