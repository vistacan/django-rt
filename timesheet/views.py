from django_rt.views import RTView, RTTemplateResponse, RTObservable, RTQueryProxy
from models import Entry
from django.contrib.auth import authenticate, login
from django.db.models import Sum
import datetime


def update_total_hours(request):

    show_declared = request.session.get('declared', False)
    total_hours = 0
    last_declared = datetime.datetime(1900, 1, 1)
    
    if request.user.is_authenticated():
    
        qs = Entry.objects.filter(
            author=request.user,
        )

        total_hours = qs.filter(
            declared__isnull=True
        ).aggregate(total_hours=Sum('hours'))['total_hours']
        if not total_hours:
            total_hours = 0

        try:
            last_declared = qs.filter(
                declared__isnull=False
            ).latest('declared')
            last_declared = last_declared.declared.strftime(
                '%Y-%m-%d %T')
        except Entry.DoesNotExist:
            last_declared = 'Never'

    return RTObservable(
        'title',
        {
            'value':'Timesheet',
            'tag':'Undeclared hours total '+str(
                total_hours
            ) + ' since ' + str(
                last_declared
            ),
            'declared': 'Show Declared Entries' if
            not show_declared else "Don't Show Declared Entries'"
        },
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
        show_declared = request.session.get('declared', False)
        if request.user.is_authenticated():
            entries = Entry.objects.filter(
                author=request.user,
                declared__isnull=not show_declared).all()[:20]
        else:
            entries =[]
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
        context['title'] = update_total_hours(self.request)
        return context

    @RTView.event('load', 'body')
    def body_load(self, request):
        if not request.user.is_authenticated():
            return LoginPanel(request)
            
        return MainPanel(request)


    @RTView.event('click', '#newbutton')
    def newbutton_click(
        self,
        request,
        newdate='#newdate',
        newhours='#newhours',
        newdescription='#newdescription'
    ):
        if not request.user.is_authenticated():
            return LoginPanel(request)
            
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
        if not request.user.is_authenticated():
            return LoginPanel(request)
        
        e = Entry.objects.get(pk=me)
        e.declared = datetime.datetime.now()
        e.save()

        RTQueryProxy.emit_change(e)

        return RTView.empty_response()

    @RTView.event('click', '#showdeclared')
    def showdeclared_click(self, request):
        if not request.user.is_authenticated():
            return LoginPanel(request)
            
        show_declared = request.session.get('declared', False)
        request.session['declared'] = not show_declared
        return MainPanel(request)
        
    @RTView.event('submit', '#login_form')
    def login_form_submit(
        self,
        request,
        username='#inputEmail',
        password='#inputPassword',
        remember_me='#rememberMe'
    ):
        # handle login
        user = authenticate(username=username.lower(), password=password)
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
