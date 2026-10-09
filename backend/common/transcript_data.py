"""Legacy eligibility on top of the shared, source-aware course contract.

Only input selection/validation is centralized in stage 1. University-specific
credit recognition and retake policy still require official verification.
"""

from .course_schema import CourseSchemaError


def valid_courses_for_analysis(transcript):
    document = transcript.get_analysis_document()
    if document is None:
        raise CourseSchemaError("분석 가능한 과목 데이터가 없습니다.")
    return [
        course for course in document["courses"]
        if course["grade"] != "F" and not course["retake"]
    ]
