"""Cohort selection shared by analysis and semester APIs."""

from .models import GraduationRequirement


def get_requirement_for_user(user):
    """Never substitute another cohort for a known admission year.

    For pre-existing users without a year, retain compatibility only if exactly
    one requirement exists for that exact major. No year is written or inferred.
    """
    if user is None or not user.major:
        return None
    requirements = GraduationRequirement.objects.filter(major=user.major)
    if user.admission_year is not None:
        return requirements.filter(year=user.admission_year).first()
    candidates = list(requirements.order_by("year", "pk")[:2])
    return candidates[0] if len(candidates) == 1 else None
