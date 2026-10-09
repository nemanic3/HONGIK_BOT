import os
from django.core.management.utils import get_random_secret_key
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 🔐 데모 키 — 실제 배포에서는 환경변수로 빼세요

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or get_random_secret_key()
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
if not DEBUG and not os.environ.get('DJANGO_SECRET_KEY'):
    raise ImproperlyConfigured('DJANGO_SECRET_KEY is required when DJANGO_DEBUG=0')
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,backend').split(',')

INSTALLED_APPS = [
    # Django 기본
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 3rd party
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    # local apps
    'users',
    'transcripts',
    'analysis',
    'semesters',
]

MIDDLEWARE = [
    'core.middleware.PrivateAPIMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',     # ← CORS는 위쪽
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Local SQLite; production uses a separate, persistent PostgreSQL instance.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    }
}

# Auth
if os.environ.get('DJANGO_DB_ENGINE') == 'postgresql':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'hongikbot'),
        'USER': os.environ.get('POSTGRES_USER', 'hongikbot'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
    if not DATABASES['default']['PASSWORD']:
        raise ImproperlyConfigured('POSTGRES_PASSWORD is required for PostgreSQL')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Locale/Time
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# Static/Media
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'media')))
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 5

# Only the authenticated Pages proxy may forward production API traffic.
HONGIK_PROXY_SECRET = os.environ.get('HONGIK_PROXY_SECRET', '')
DJANGO_REQUIRE_PROXY_SECRET = os.environ.get('DJANGO_REQUIRE_PROXY_SECRET', '0') == '1'
if DJANGO_REQUIRE_PROXY_SECRET and len(HONGIK_PROXY_SECRET) < 32:
    raise ImproperlyConfigured('HONGIK_PROXY_SECRET must contain at least 32 characters')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if DJANGO_REQUIRE_PROXY_SECRET else None
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
# Scoped to this service hostname; sibling sites receive no changed settings.
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_TRUSTED_ORIGINS = [v for v in os.environ.get('DJANGO_CSRF_ORIGINS', '').split(',') if v]

# DRF + JWT(auth class만 등록)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# Custom User
AUTH_USER_MODEL = 'users.User'

# CORS (개발 편의)
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [v for v in os.environ.get('DJANGO_CORS_ORIGINS', 'http://127.0.0.1:3000,http://127.0.0.1:3001').split(',') if v]

# Celery — Redis 브로커/결과 백엔드 사용(권장)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'

# Explicit local mode; never silently pretend a queued task is running.
TRANSCRIPT_PROCESSING = os.environ.get('TRANSCRIPT_PROCESSING', 'celery')
# Optional dotted callable: PNG bytes -> {'text': str, 'provider': str, ...}.
# No heavyweight Paddle imports or fabricated image text by default.
TRANSCRIPT_IMAGE_OCR_PROVIDER = os.environ.get('TRANSCRIPT_IMAGE_OCR_PROVIDER', '')
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_TIMEOUT = 2

# Bound worker resource use; a soft timeout is recorded as a recoverable error.
CELERY_TASK_SOFT_TIME_LIMIT = 600
CELERY_TASK_TIME_LIMIT = 660
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SEND_SENT_EVENT = False
