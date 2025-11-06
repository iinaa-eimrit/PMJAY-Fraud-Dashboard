"""
Django settings for pmjay_fraud_dashboard project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-z$^vko)vy-r2*4%61%)bvbcb@!ik6($9jun+92sby)vds!hw3@')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pmjay_fraud_dashboard_app',
    'corsheaders',
    'django_apscheduler',
    'django_extensions',
    'pmjay_fraud_dashboard_show_cause_engine',
    'pmjay_fraud_dashboard_penalty_engine'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pmjay_fraud_dashboard_app.utils.middleware.RequestContextMiddleware',
]

ROOT_URLCONF = 'pmjay_fraud_dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pmjay_fraud_dashboard.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        'CONN_MAX_AGE': 0,  # Disable persistent connections to avoid locks
        'OPTIONS': {
            'timeout': 30,  # Increase timeout from default 5 to 30 seconds
            'isolation_level': None,  # Enable autocommit mode
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    # ... keep your existing validators
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = False

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = False

APSCHEDULER_RUN_NOW_TIMEOUT = 300

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'context_filter': {
            '()': 'pmjay_fraud_dashboard_app.utils.logging.ContextFilter',
        },
    },
    'formatters': {
        'structured': {
            'format': 'time="%(asctime)s" level="%(levelname)s" logger="%(name)s" request_id="%(request_id)s" feature="%(feature)s" endpoint="%(endpoint)s" execution_time_ms="%(execution_time_ms)s" message="%(message)s"',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['context_filter'],
            'formatter': 'structured',
        },
    },
    'loggers': {
        'pmjay_dashboard': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
APSCHEDULER_DATETIME_FORMAT = "N j, Y, f:s a"


# ============================
# EMAIL CONFIGURATION
# ============================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.mail.yahoo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'abnhpmbihar@yahoo.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'PMJAY Fraud Monitoring <abnhpmbihar@yahoo.com>')

# Set to True to bypass timing checks in show cause engine for testing purposes
SHOW_CAUSE_BYPASS_TIMING = False