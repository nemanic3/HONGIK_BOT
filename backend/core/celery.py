"""One Django-configured Celery app shared by API publishers and OCR workers."""
import os
from celery import Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
app = Celery('hongik')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
