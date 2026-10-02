from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # APIs
    path('api/users/', include('users.urls')),
    path('api/transcripts/', include('transcripts.urls')),
    path('api/analysis/', include('analysis.urls')),
    path('api/semesters/', include('semesters.urls')),
]
