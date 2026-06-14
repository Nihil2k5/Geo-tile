"""
Django settings for geoledger project.
"""

from pathlib import Path
import os
import json
from cryptography.fernet import Fernet

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-your-secret-key'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Generate a valid Fernet key for wallet encryption
# Using a fixed key for development - in production, this should be from environment variables
ENCRYPTION_KEY = 'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for Site framework (used in emails)
    'land_registry',
    'theme',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'land_registry.middleware.RoleMiddleware',
]

ROOT_URLCONF = 'geoledger.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'land_registry' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'land_registry.context_processors.licensing_admin_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'geoledger.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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

# Custom User Model
AUTH_USER_MODEL = 'land_registry.User'

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files (Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Web3 and Blockchain Settings
WEB3_PROVIDER_URI = 'http://127.0.0.1:8545'  # Local Hardhat node

# Admin wallet for contract interactions
# This is the first account from Hardhat's default accounts
ADMIN_ADDRESS = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'
ADMIN_PRIVATE_KEY = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'

# Contract Addresses
try:
    with open(BASE_DIR / 'blockchain' / 'contract-addresses.json', 'r') as f:
        CONTRACT_ADDRESSES = json.load(f)
except FileNotFoundError:
    CONTRACT_ADDRESSES = {
        'UserRegistry': None,
        'LandRegistry': None,
        'DisputeManager': None
    }

# Contract ABIs
try:
    with open(BASE_DIR / 'blockchain' / 'contract-abis.json', 'r') as f:
        artifacts = json.load(f)
        CONTRACT_ABIS = {
            name: artifact['abi'] for name, artifact in artifacts.items()
        }
except FileNotFoundError:
    CONTRACT_ABIS = {
        'UserRegistry': None,
        'LandRegistry': None,
        'DisputeManager': None
    }

# IPFS settings
IPFS_HOST = 'localhost'
IPFS_PORT = 5001

# Mapbox settings
MAPBOX_TOKEN = 'pk.eyJ1IjoibmloaWw3MDciLCJhIjoiY2x5cmUyZ2ZoMDdpNTJyczYwcHRvb2F4NCJ9.fqLPFm4FokiklI0MQzlpzA'

# Login URL
LOGIN_URL = 'land_registry:login'
LOGIN_REDIRECT_URL = 'land_registry:dashboard'

# Email Configuration
# For development: Use console backend (emails printed to console)
# For production: Configure SMTP settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Development
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Production

# SMTP Settings (uncomment and configure for production)
EMAIL_HOST = 'smtp.gmail.com'  # or your SMTP server
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'felizsas2k@gmail.com'
EMAIL_HOST_PASSWORD = 'epng szgh xmwz qazy'
DEFAULT_FROM_EMAIL = 'felizsas2k@gmail.com'  # Change this to your actual email
SERVER_EMAIL = DEFAULT_FROM_EMAIL
