import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = ["routing"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]
DATABASES = {}  #no DB needed: station data is loaded into memory at first use
USE_TZ = True

#Route results are cached so repeat requests make zero external calls (as asked in the assignment)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

FUEL = {
    "MAX_RANGE_MILES": 500.0,
    "MPG": 10.0,
    "CORRIDOR_MILES": 10.0,  # max distance a station may sit from the route
    "OSRM_URL": os.environ.get("OSRM_URL", "https://router.project-osrm.org"),
    "NOMINATIM_URL": "https://nominatim.openstreetmap.org",
    "HTTP_TIMEOUT": 10,
    "USER_AGENT": "fuelroute-assessment/1.0",
    "CACHE_SECONDS": 60 * 60 * 24,
}
