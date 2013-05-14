from django_rt.views import RTView, RTTemplateResponse, RTObservable, RTQueryProxy
from models import Entry
from django.contrib.auth import authenticate, login
from django.db.models import Sum


def update_total_hours(request):
    total_hours = Entry.objects.filter(
        author=request.user,
        declared__exact=False
    ).aggregate(total_hours=Sum('hours'))['total_hours']
    RTObservable(
        'title',
        {
            'value':'Timesheet',
            'tag':'Undeclared hours total '+str(total_hours)},
        app_label = request.session.session_key
    ).set_changed()


class LoginPanel(RTTemplateResponse):
    def __init__(self, request, msg=None):
        super(LoginPanel, self).__init__(
            request,
            'timesheet_login.html',
            {'message':msg},
            target_query='.contents'
        )

        
class MainPanel(RTTemplateResponse):
    def __init__(self, request):
        entries = Entry.objects.filter(
            author=request.user, declared__exact=False).all()
        update_total_hours(request)
        super(MainPanel, self).__init__(
            request,
            'timesheet_main.html',
            {'entries':entries},
            target_query='.contents'
        )


class MainView(RTView):
    template_name = 'timesheet_base.html'
    def get_context_data(self, **kwargs):
        context = super(MainView, self).get_context_data(**kwargs)
        context['title'] = RTObservable(
            'title', {'value':'Timesheet', 'tag':'Welcome'},
            app_label = self.request.session.session_key
        )
        return context

    @RTView.event('load', 'body')
    def body_load(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated():
            return MainPanel(request)
        else:
            return LoginPanel(request)

    @RTView.event('click', '#newbutton')
    def newbutton_click(
        self,
        request,
        newdate='#newdate',
        newhours='#newhours',
        newdescription='#newdescription'
    ):
        Entry(
            date=newdate,
            hours=newhours,
            description=newdescription,
            author=request.user
        ).save()

        update_total_hours(request)
        
        return RTView.empty_response()

    @RTView.event('click', 'button.declare')
    def selected_click(self, request, me="$(this)"):
        e = Entry.objects.get(pk=me)
        e.declared = True
        e.save()

        RTQueryProxy.emit_change(e)

        return RTView.empty_response()
        
    @RTView.event('submit', '#login_form')
    def login_form_submit(
        self,
        request,
        username='#inputEmail',
        password='#inputPassword',
        remember_me='#rememberMe'
    ):
        # handle login
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if not remember_me is None:
                    request.session.set_expiry(0)
                return MainPanel(request)
            else:
                message = 'Not active?'
        else:
            message = 'Bad login?'
            
        RTObservable(
            'title',
            {'value':'Timesheet', 'tag':message},
            app_label = request.session.session_key
        ).set_changed()
        
        return LoginPanel(request, message)
