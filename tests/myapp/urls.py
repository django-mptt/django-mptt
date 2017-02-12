import django
from django.conf.urls import include, url

from django.contrib import admin


if django.VERSION >= (1, 9):
    urlpatterns = [url(r'^admin/', admin.site.urls)]
else:
    urlpatterns = [url(r'^admin/', include(admin.site.urls))]
