from django.conf.urls import patterns, include, url
from views import RTJavascriptEvents, RTManagement
from django.views.decorators.csrf import ensure_csrf_cookie
import timesheet.urls
from django.views.generic.simple import redirect_to


urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'django_rt.views.home', name='home'),
    # url(r'^django_rt/', include('django_rt.foo.urls')),
    
    url(r'^rt/admin', RTManagement.as_view(), name='admin'),
    url(r'^rt/application.js', ensure_csrf_cookie(RTJavascriptEvents.as_view()), name='application_js'),
    url(r'^time/.*', include(timesheet.urls)),
    url(r'.*', redirect_to, {'url': '/time/'}),
                       
    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)
