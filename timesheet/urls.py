from django.conf.urls import patterns, include, url
from views import MainView
from django.views.decorators.csrf import ensure_csrf_cookie


urlpatterns = patterns(
    '',
    url(r'.*', ensure_csrf_cookie(MainView.as_view()), name='main'),
)