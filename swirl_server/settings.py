'''
Django settings for swirl_server project.

Generated by 'django-admin startproject' using Django 4.0.1.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.0/ref/settings/
'''

from pathlib import Path
import environ
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# PUT the FQDN first in the list below
ALLOWED_HOSTS = list(env('ALLOWED_HOSTS').split(','))
HOSTNAME = ALLOWED_HOSTS[0]
PROTOCOL = env('PROTOCOL')

# Application definition

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    'swirl',
    'rest_framework',
    'celery',
    'django_celery_beat',
    'rest_framework_swagger',
    'rest_framework.authtoken',
    'django.contrib.admin',
    'django.contrib.auth',
    'channels',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'drf_yasg'
]

ASGI_APPLICATION = 'swirl_server.routing.application'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'swirl.middleware.TokenMiddleware',
    'swirl.middleware.SpyglassAuthenticatorsMiddleware',
    'swirl.middleware.SwaggerMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'swirl_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'swirl_server.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': str(env('SQL_ENGINE')),
        'NAME': env('SQL_DATABASE'),
        'USER': env('SQL_USER'),
        'PASSWORD': env('SQL_PASSWORD'),
        'HOST': env('SQL_HOST'),
        'PORT': int(env('SQL_PORT'))
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'sid',
#         'USER': 'sid',
#         'PASSWORD': 'sid',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'US/Eastern'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/

if DEBUG:
    STATIC_URL = 'static/'
else:
    STATIC_URL = '/'

MEDIA_ROOT = 'uploads/'
MEDIA_URL = 'uploads/'

import os

STATIC_ROOT = os.path.join(BASE_DIR, 'static/')

STATICFILES_DIRS = []

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CELERY
from celery.schedules import crontab

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']


CELERY_TASK_ALWAYS_EAGER = False

CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = False

# Celery Configuration Options
CELERY_TIMEZONE = 'US/Eastern'
CELERY_TIME_ZONE = 'US/Eastern'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {
    # Executes every hour
    'expire': {
         'task': 'expirer',
         'schedule': crontab(minute=0,hour='*'),
        },
    # Executes every four hours
    'subscribe': {
         'task': 'subscriber',
         'schedule': crontab(minute=0,hour='*/4'),   # minute='*/10'
        },
}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_URL_DEF = 'redis://localhost:6379/0'
CELERY_BROKER_URL = env('CELERY_BROKER_URL',default=CELERY_BROKER_URL_DEF)

CELERY_RESULT_BACKEND_DEF = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=CELERY_RESULT_BACKEND_DEF)

# EMAIL

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_sendgrid_username'
EMAIL_HOST_PASSWORD = 'your_sendgrid_password'

#####################################
# SWIRL SEARCH

SWIRL_DEFAULT_QUERY_LANGUAGE = 'english'
SWIRL_TIMEOUT_DEFAULT = 10
SWIRL_TIMEOUT = env.int('SWIRL_TIMEOUT',default=SWIRL_TIMEOUT_DEFAULT)
SWIRL_SUBSCRIBE_WAIT = 20
SWIRL_DEDUPE_FIELD = 'url'
SWIRL_DEDUPE_SIMILARITY_MINIMUM = 0.95
SWIRL_DEDUPE_SIMILARITY_FIELDS = ['title', 'body']

SWIRL_EXPLAIN = bool(env('SWIRL_EXPLAIN'))

SWIRL_RELEVANCY_CONFIG = {
    'title': {
        'weight': 1.5
    },
    'body': {
        'weight': 1.0
    },
    'author': {
        'weight': 1.0
    }
}

SWIRL_MAX_MATCHES = 5
SWIRL_MIN_SIMILARITY_DEFAULT = 0.01
SWIRL_MIN_SIMILARITY = env.float('SWIRL_MIN_SIMILARITY', default=SWIRL_MIN_SIMILARITY_DEFAULT)

# SWIRL_MAX_TEMPORAL_DISTANCE = 90
# SWIRL_MAX_TEMPORAL_DISTANCE_UNITS = 'days' # days | hours

# SWIRL_MIN_RELEVANCY_SCORE = 50.0

SWIRL_HIGHLIGHT_START_CHAR = '<em>'
SWIRL_HIGHLIGHT_END_CHAR = '</em>'

SWIRL_SEARCH_FORM_URL_DEF = '/swirl/search.html'
SWIRL_SEARCH_FORM_URL = env('SWIRL_SEARCH_FORM_URL', default=SWIRL_SEARCH_FORM_URL_DEF)

SWIRL_DEFAULT_RESULT_BLOCK = 'ai_summary'

OPENAI_API_KEY = env.get_value('OPENAI_API_KEY', default='')

MICROSOFT_CLIENT_ID= env('MICROSOFT_CLIENT_ID')
MICROSOFT_CLIENT_SECRET = env('MICROSOFT_CLIENT_SECRET')
MICROSOFT_REDIRECT_URI = env('MICROSOFT_REDIRECT_URI')

CSRF_TRUSTED_ORIGINS = ['http://localhost:4200']

SWIRL_WRITE_PATH_DEF = 'stored_results'
SWIRL_WRITE_PATH = env('SWIRL_WRITE_PATH', default=SWIRL_WRITE_PATH_DEF)

SWIRL_MAX_FIELD_LEN = 512

CHANNEL_LAYERS = {
    'default': {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(CELERY_BROKER_URL)],
            'capacity': 300
        },
    },
}
ASGI_THREADS = 1000

DISCORD_BOT_TOKEN = env("DISCORD_BOT_TOKEN")
COHERE_API_KEY = env("COHERE_API_KEY")
QDRANT_API_KEY = env("QDRANT_API_KEY")
QDRANT_URL = env("QDRANT_URL")
