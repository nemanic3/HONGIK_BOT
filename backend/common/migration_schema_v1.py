"""Frozen schema v1 for historical data migrations. Never edit after release.

Future schema revisions must use a new module. Runtime validation lives in
course_schema.py; migration behavior must remain stable independently of it.
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

SCHEMA_VERSION = 1
REQUIREMENT_COURSE_FIELDS = (
    "major_must_courses",
    "major_selective_courses",
    "general_must_courses",
    "general_selective_courses",
    "special_general_courses",
    "sw_courses",
    "msc_courses",
)


class CourseSchemaError(ValueError):
    """An input cannot be represented without guessing or discarding data."""


def normalize_credit(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise CourseSchemaError("credit는 음수가 아닌 유한한 숫자 또는 null이어야 합니다.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise CourseSchemaError("credit를 숫자로 읽을 수 없습니다.") from exc
    if not number.is_finite() or number < 0:
        raise CourseSchemaError("credit는 음수가 아닌 유한한 숫자여야 합니다.")
    result = float(number)
    if not isfinite(result) or (number != 0 and result == 0):
        raise CourseSchemaError("credit가 JSON 숫자 범위를 벗어났습니다.")
    if number == number.to_integral_value():
        return int(number)
    return result


def normalize_course_reference(value):
    """Accept legacy names or objects; preserve identifiers and extra metadata."""
    if isinstance(value, str):
        value = {"name": value}
    if not isinstance(value, dict):
        raise CourseSchemaError("과목은 이름 문자열 또는 객체여야 합니다.")
    result: dict[str, Any] = deepcopy(value)
    if "credit" in result:
        result["credit"] = normalize_credit(result["credit"])
    for field in ("code", "name"):
        result.setdefault(field, "")
        if not isinstance(result[field], str):
            raise CourseSchemaError(f"{field}는 문자열이어야 합니다.")
    if not (result["code"].strip() or result["name"].strip()):
        raise CourseSchemaError("과목 코드 또는 이름이 필요합니다.")
    result.setdefault("semester", None)
    if result["semester"] is not None and not isinstance(result["semester"], str):
        raise CourseSchemaError("semester는 문자열 또는 null이어야 합니다.")
    result.setdefault("aliases", [])
    if not isinstance(result["aliases"], list) or any(
        not isinstance(alias, str) for alias in result["aliases"]
    ):
        raise CourseSchemaError("aliases는 문자열 배열이어야 합니다.")
    return result


def normalize_course_references(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise CourseSchemaError("과목 목록은 배열이어야 합니다.")
    return [normalize_course_reference(item) for item in value]


def normalize_area_courses(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or any(not isinstance(area, str) for area in value):
        raise CourseSchemaError("영역별 과목은 영역 이름을 키로 하는 객체여야 합니다.")
    return {area: normalize_course_references(items) for area, items in value.items()}


def normalize_course(value, *, for_confirmation=False):
    if not isinstance(value, dict):
        raise CourseSchemaError("이수 과목은 객체여야 합니다. OCR 셀은 자동으로 추정하지 않습니다.")
    result = normalize_course_reference(value)
    result.setdefault("credit", None)
    for field in ("grade", "type", "major_field"):
        result.setdefault(field, "")
        if not isinstance(result[field], str):
            raise CourseSchemaError(f"{field}는 문자열이어야 합니다.")
    result.setdefault("retake", False)
    if not isinstance(result["retake"], bool):
        raise CourseSchemaError("retake는 boolean이어야 합니다.")
    result.setdefault("academic_year", None)
    year = result["academic_year"]
    if year is not None and (type(year) is not int or not 1000 <= year <= 9999):
        raise CourseSchemaError("academic_year는 4자리 연도 또는 null이어야 합니다.")
    result.setdefault("term", None)
    if result["term"] is not None and not isinstance(result["term"], str):
        raise CourseSchemaError("term은 문자열 또는 null이어야 합니다.")
    if for_confirmation:
        for field in ("name", "grade", "semester", "type"):
            if not isinstance(result[field], str) or not result[field].strip():
                raise CourseSchemaError(f"확정하려면 {field}가 필요합니다.")
        if result["credit"] is None:
            raise CourseSchemaError("확정하려면 credit가 필요합니다.")
    return result


def normalize_course_document(value, *, for_confirmation=False):
    """Adapt object/list legacy data; raw OCR text and rows remain raw only."""
    if isinstance(value, list):
        value = {"courses": value}
    if not isinstance(value, dict) or "courses" not in value:
        raise CourseSchemaError("courses 배열을 가진 객체가 필요합니다.")
    version = value.get("schema_version", SCHEMA_VERSION)
    if type(version) is not int or version != SCHEMA_VERSION:
        raise CourseSchemaError("지원하지 않는 과목 스키마 버전입니다.")
    if not isinstance(value["courses"], list):
        raise CourseSchemaError("courses는 배열이어야 합니다.")
    document = deepcopy(value)
    courses = []
    for index, item in enumerate(value["courses"]):
        try:
            courses.append(normalize_course(item, for_confirmation=for_confirmation))
        except CourseSchemaError as exc:
            raise CourseSchemaError(f"courses[{index}]: {exc}") from exc
    document["schema_version"] = SCHEMA_VERSION
    document["courses"] = courses
    return document
