from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from .models import RequirementRuleSet, GraduationRequirement


class LoadRulesTests(TestCase):
    def test_dry_run_is_default_and_import_does_not_replace_legacy_data(self):
        legacy=GraduationRequirement.objects.create(major='컴퓨터공학과',year=2025,total_required=132,major_must_courses=[])
        output=StringIO()
        call_command('load_curriculum_rules',stdout=output)
        self.assertEqual(RequirementRuleSet.objects.count(),0)
        call_command('load_curriculum_rules',apply=True,stdout=output)
        count=RequirementRuleSet.objects.count()
        self.assertGreater(count,0)
        call_command('load_curriculum_rules',apply=True,stdout=output)
        self.assertEqual(RequirementRuleSet.objects.count(),count)
        self.assertFalse(RequirementRuleSet.objects.filter(source_verified=True).exists())
        self.assertEqual(GraduationRequirement.objects.get(pk=legacy.pk).total_required,132)
