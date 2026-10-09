"""Validate before optional import; never overwrite legacy graduation thresholds."""
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from analysis.models import RequirementRuleSet
from analysis.policy import bundle


class Command(BaseCommand):
    help = 'Validate provided PDF rules; --apply explicitly adds immutable draft versions.'

    def add_arguments(self, parser):
        parser.add_argument('--apply',action='store_true',help='Write versioned rule records; default is read-only validation.')

    def handle(self, *args, **options):
        rows=bundle()['policies']
        try:
            for row in rows:
                RequirementRuleSet(**row).clean()
        except (ValidationError, TypeError) as exc:
            raise CommandError(f'Invalid policy bundle: {exc}') from exc
        if not options['apply']:
            self.stdout.write(f'Validated {len(rows)} draft policies; no database writes.')
            return
        added=0
        with transaction.atomic():
            for row in rows:
                keys={key:row[key] for key in ['major','campus','admission_year_from','admission_year_to','accreditation_track','version']}
                existing=RequirementRuleSet.objects.filter(**keys).first()
                if existing:
                    if any(getattr(existing,key)!=value for key,value in row.items()):
                        raise CommandError('Existing rule version differs; create a new version instead of overwriting.')
                    continue
                RequirementRuleSet.objects.create(**row)
                added+=1
        self.stdout.write(f'Added {added} unverified draft rule sets; legacy rows unchanged.')
