from django.contrib import admin
from .models import CourseIdentity, CourseVersion, CourseEvidence, CourseRelation


class PreservedHistoryAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CourseIdentity)
class CourseIdentityAdmin(PreservedHistoryAdmin):
    list_display = ('id', 'created_at')
    readonly_fields = ('id', 'created_at')


@admin.register(CourseEvidence)
class CourseEvidenceAdmin(PreservedHistoryAdmin):
    list_display = ('document', 'pdf_page', 'official_verified', 'verified_by', 'verified_at')
    list_filter = ('official_verified',)
    search_fields = ('document', 'statement')


@admin.register(CourseVersion)
class CourseVersionAdmin(PreservedHistoryAdmin):
    list_display = ('code', 'name', 'academic_year', 'term', 'credit', 'classification', 'course')
    list_filter = ('academic_year', 'term', 'campus', 'major')
    search_fields = ('code', 'name')

    def get_readonly_fields(self, request, obj=None):
        return tuple(f.name for f in self.model._meta.fields) if obj else ()


@admin.register(CourseRelation)
class CourseRelationAdmin(PreservedHistoryAdmin):
    list_display = ('source', 'target', 'kind', 'policy_version', 'criterion_id', 'evidence')
    list_filter = ('kind',)
