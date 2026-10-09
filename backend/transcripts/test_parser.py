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
