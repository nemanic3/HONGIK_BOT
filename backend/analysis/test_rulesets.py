from django.test import TestCase
from django.core.exceptions import ValidationError
from .models import RequirementRuleSet


class RuleSetTests(TestCase):
    def test_tracks_do_not_share_a_requirement_record(self):
        values = dict(major='컴퓨터공학과', admission_year_from=2024, admission_year_to=2026, curriculum_year=2026, version='pdf-2026-draft', data={'schema_version':1, 'criteria':[{'id':'review', 'kind':'review', 'source':{'pdf_page':1,'printed_page':'fixture-1'}}], 'catalog':[]}, source_document='fixture', source_sha256='0'*64)
        for track in ['accredited', 'non_accredited']:
            RequirementRuleSet.objects.create(accreditation_track=track, **values)
        self.assertEqual(RequirementRuleSet.objects.count(), 2)

    def test_invalid_range_or_missing_evidence_is_rejected(self):
        row = RequirementRuleSet(major='학과', admission_year_from=2026, admission_year_to=2024, curriculum_year=2026, accreditation_track='non_accredited', version='test', data={'schema_version':1, 'criteria':[], 'catalog':[]}, source_document='fixture', source_sha256='0'*64)
        with self.assertRaises(ValidationError):
            row.full_clean()
