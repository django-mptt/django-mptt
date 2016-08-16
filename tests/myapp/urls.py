from django.conf.urls import url

from django.contrib import admin


admin.autodiscover()


urlpatterns = [
    url(r'^admin/', admin.site.urls),
]
