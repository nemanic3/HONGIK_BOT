from copy import deepcopy
from io import BytesIO
from django.test import SimpleTestCase, override_settings
from .parser import parse_course_pages
from .spatial import merge_captures


def table(offset=0, semester='2030학년도 1학년 1학기', code='009001', grade='A0'):
    def b(text,x,y,width=.045):
        return dict(text=text,x=x+offset,y=y,width=width,height=.02,confidence=.99)
    xs=[.01,.10,.28,.35,.40]
    boxes=[b(semester,.01,.02,.40)]
    boxes += [b(t,x,.1) for t,x in zip(['학수번호','과목명','이수구분','학점','성적'],xs)]
    boxes += [b(t,x,.2) for t,x in zip([code,'가상과목','전선','3',grade],xs)]
    return boxes


def parse(boxes, number=1):
    return parse_course_pages({'pages':[{'file_number':number,'page_number':1,'observations':boxes,'text':'fixture'}]})


class MultiCaptureTests(SimpleTestCase):
    def test_two_columns_keep_separate_terms_and_coordinates(self):
        doc=parse(table()+table(.5,'2031학년도 2학년 2학기'))
        a,b=doc['courses']
        self.assertEqual([a['semester'],b['semester']],['2030-1','2031-2'])
        self.assertEqual([a['sources'][0]['column'],b['sources'][0]['column']],[1,2])
        self.assertTrue(a['retake_candidate'])

    def test_wrapped_name_uses_next_line_without_merging_next_course(self):
        boxes=table()
        boxes.append(dict(text='줄바꿈',x=.1,y=.225,width=.05,height=.018,confidence=.99))
        doc=parse(boxes)
        self.assertEqual(doc['courses'][0]['name'],'가상과목 줄바꿈')

    def test_identical_capture_merges_provenance_not_semesters(self):
        a=parse(table(),1)['courses'][0];b=parse(table(),2)['courses'][0]
        merged=merge_captures([a,b])
        self.assertEqual(len(merged),1)
        self.assertEqual(len(merged[0]['sources']),2)
        self.assertTrue(merged[0]['capture_overlap'])
        c=parse(table(semester='2031학년도 2학년 1학기'),3)['courses'][0]
        self.assertEqual(len(merge_captures([merged[0],c])),2)

    def test_same_term_conflicting_grade_keeps_both(self):
        rows=merge_captures([parse(table(),1)['courses'][0],parse(table(grade='C+'),2)['courses'][0]])
        self.assertEqual(len(rows),2)
        self.assertTrue(all(c['capture_conflict'] for c in rows))

    def test_unknown_semester_never_deduplicates(self):
        rows=[parse(table()[1:],n)['courses'][0] for n in [1,2]]
        self.assertEqual(len(merge_captures(rows)),2)

    def test_ambiguous_grade_credit_remain_unmodified(self):
        boxes=table(grade='AO')
        next(b for b in boxes if b['text']=='3')['text']='A'
        row=parse(boxes)['courses'][0]
        self.assertEqual(row['grade'],'AO');self.assertIsNone(row['credit'])
        self.assertIn('성적 확인',row['review_reasons'])

    def test_missing_header_marks_incomplete(self):
        doc=parse([b for b in table() if b['text']!='성적'])
        self.assertFalse(doc['courses']);self.assertTrue(doc['incomplete'])

    def test_transient_image_error_retries_once(self):
        from PIL import Image
        from .reader import read_document
        out=BytesIO();Image.new('RGB',(20,20),'white').save(out,format='PNG')
        calls=[]
        def provider(_):
            calls.append(1)
            if len(calls)==1: raise ConnectionError('private error')
            return {'text':'fixture'}
        self.assertEqual(read_document(BytesIO(out.getvalue()),image_provider=provider)['pages'][0]['text'],'fixture')
        self.assertEqual(len(calls),2)

    def test_clipped_continuation_reuses_columns_but_not_semester(self):
        second=[b for b in table(code='009002') if b['y']>.15]
        doc=parse_course_pages({'pages':[{'file_number':1,'page_number':1,'observations':table()},{'file_number':2,'page_number':1,'observations':second}]})
        self.assertEqual(len(doc['courses']),2)
        self.assertEqual(doc['courses'][1]['code'],'009002')
        self.assertIsNone(doc['courses'][1]['semester'])
        self.assertTrue(doc['incomplete'])

    def test_unreadable_code_produces_visible_missing_row_warning(self):
        doc=parse([b for b in table() if b['text']!='009001'])
        self.assertIn('unassigned_row',[w['code'] for w in doc['warnings']])

    def test_tile_coordinates_map_back_to_full_image(self):
        from .paddle_provider import observation_boxes
        boxes=observation_boxes({'rec_texts':['Fixture'],'rec_scores':[.8],'rec_polys':[[[10,20],[110,20],[110,40],[10,40]]]},1000,4000,1840)
        self.assertEqual(boxes[0]['y'],.465)
        self.assertEqual(boxes[0]['height'],.005)
        self.assertEqual(boxes[0]['confidence'],.8)

    def test_empty_image_result_is_reported_as_failure(self):
        from PIL import Image
        from .reader import read_document
        out=BytesIO();Image.new('RGB',(20,20),'white').save(out,format='PNG')
        result=read_document(BytesIO(out.getvalue()),image_provider=lambda _: {'text':''})
        self.assertEqual(result['warnings'][0]['code'],'ocr_failed')

    def test_soft_timeout_propagates_to_task_error_handler(self):
        from PIL import Image
        from .reader import read_document
        from billiard.exceptions import SoftTimeLimitExceeded
        out=BytesIO();Image.new('RGB',(20,20),'white').save(out,format='PNG')
        def timed_out(_):raise SoftTimeLimitExceeded()
        with self.assertRaises(SoftTimeLimitExceeded):read_document(BytesIO(out.getvalue()),image_provider=timed_out)
