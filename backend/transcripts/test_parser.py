from django.test import SimpleTestCase
from .test_reader import HEADER, ROW


class ParserTests(SimpleTestCase):
    def test_unknown_layout_remains_unparsed_not_zero_credit_completion(self):
        from .parser import parse_course_pages
        doc = parse_course_pages({'pages': [{'page_number': 1, 'text': 'Transcript\n001009 English 3 A+\nTotal 3'}], 'warnings': []})
        self.assertEqual(doc['courses'], [])
        self.assertTrue(doc['warnings'])
        self.assertEqual(len(doc['unparsed_lines']), 3)
        self.assertTrue(doc['incomplete'])

    def test_partial_rows_keep_valid_rows_and_missing_values_without_guessing(self):
        from .parser import parse_course_pages
        text = 'fixture title\n' + HEADER + '\n' + ROW + '\n001010 | Writing | | | | |\n001011 | Broken | many | B | 1-1 | General | Required\nextra unknown line'
        doc = parse_course_pages({'pages': [{'page_number': 2, 'text': text}], 'warnings': []})
        self.assertEqual(len(doc['courses']), 2)
        self.assertIsNone(doc['courses'][1]['credit'])
        self.assertEqual(doc['courses'][1]['type'], '')
        self.assertEqual(len(doc['unparsed_lines']), 3)
        self.assertTrue(doc['incomplete'])
        self.assertTrue(doc['warnings'])

    def test_korean_explicit_columns_map_without_translating_values(self):
        from .parser import parse_course_pages
        text = '학수번호\t교과목명\t학점\t성적\t학기\t이수구분\t영역\n001009\t영어\t3\tA+\t1-1\t교양\t교양필수'
        doc = parse_course_pages({'pages': [{'page_number': 1, 'text': text}], 'warnings': []})
        self.assertEqual(doc['courses'][0]['name'], '영어')
        self.assertEqual(doc['courses'][0]['type'], '교양')

    def test_explicit_columns_produce_courses_preserving_identifiers(self):
        from .parser import parse_course_pages
        doc = parse_course_pages({'pages': [{'page_number': 1, 'text': HEADER + '\n' + ROW}], 'warnings': []})
        self.assertEqual(doc['schema_version'], 1)
        self.assertEqual(doc['courses'][0]['code'], '001009')
        self.assertEqual(doc['courses'][0]['name'], 'English')
        self.assertEqual(doc['courses'][0]['credit'], 3)
        self.assertEqual(doc['courses'][0]['major_field'], 'Required')
        self.assertTrue(doc['needs_review'])
        self.assertEqual(doc['warnings'], [])

    def test_spatial_columns_restore_rows_with_empty_cells_and_retakes(self):
        from .parser import parse_course_pages
        def box(text, x, y, width=.08):
            return dict(text=text, x=x, y=y, width=width, height=.025)
        headers = ['학수번호', '과목명', '영문과목명', '학점', '성적', '재수강']
        positions = [.02, .20, .43, .72, .82, .92]
        boxes = [box('2030학년도 1학년 1학기', .02, .01)]
        boxes += [box(t, x, .1) for t, x in zip(headers, positions)]
        for y, row in [(.2, ['009001', '테스트과목', 'TEST COURSE', '3', 'A0', '']),
                       (.3, ['009002', '가상과목', 'DEMO COURSE', '2', 'C+', '재수강'])]:
            boxes += [box(t, x, y) for t, x in zip(row, positions) if t]
        # Column-first OCR order must not affect the restored rows.
        boxes.sort(key=lambda b: b['x'])
        doc = parse_course_pages({'pages': [{'page_number': 1, 'observations': boxes, 'text': ''}]})
        self.assertEqual(len(doc['courses']), 2)
        first, second = doc['courses']
        self.assertEqual((first['code'], first['name'], first['credit'], first['grade']),
                         ('009001', '테스트과목', 3, 'A0'))
        self.assertEqual(first['semester'], '2030-1')
        self.assertFalse(first['retake'])
        self.assertTrue(second['retake'])
        self.assertEqual(second['english_name'], 'DEMO COURSE')
        self.assertEqual(first['type'], '')
        self.assertTrue(doc['incomplete'])

    def test_spatial_adjacent_tables_are_not_combined(self):
        from .parser import parse_course_pages
        boxes = []
        for offset in [0, .5]:
            for x, text in [(.01,'학수번호'),(.12,'과목명'),(.24,'학점')]:
                boxes.append(dict(text=text,x=x+offset,y=.1,width=.08,height=.03))
            for x, text in [(.01,'009001'),(.12,'테스트'),(.24,'3')]:
                boxes.append(dict(text=text,x=x+offset,y=.2,width=.08,height=.03))
        doc = parse_course_pages({'pages':[{'page_number':1,'observations':boxes}]})
        self.assertEqual(doc['courses'], [])
        self.assertTrue(doc['incomplete'])
