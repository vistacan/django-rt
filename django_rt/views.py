from django.views.generic import TemplateView
from django.template.response import TemplateResponse
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Model
from django.db.models.query import QuerySet
from django.core.urlresolvers import reverse
from django.utils.safestring import SafeString
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict

from util import itersubclasses, RTEncoder

from urllib import quote
from functools import wraps
import json
from uuid import uuid4
import redis
from inspect import getargspec
import base64
import traceback
import StringIO


redis_pool = redis.ConnectionPool()
HTTP_X_EVENT_ID = 'HTTP_X_EVENT_ID'
RT_SCRIPT = '''
<script type="text/javascript"
    src="//ajax.googleapis.com/ajax/libs/jquery/2.0.0/jquery.min.js">
</script>
<script type="text/javascript" src="/static/jquery.cookie.js"></script>
<script type="text/javascript" src="/static/util.js"></script>
<script type="text/javascript">
    script("%s", function(){
        console.log('Loaded: application.js');
        script(
            "//"+document.domain+":8887/socket.io/socket.io.js",
            function(){
                console.log('Loaded: socket.io.js');
                $(function(){
                    rtinit(true, function(){init_socket();});
                });
            }
        );
    });
</script>
'''


class Struct():
    def __init__(self, **entries):
        self.__dict__.update(entries)


class RTObservable(object):

    skip_fields=set()
    
    def __init__(self, name, obj, app_label=None, id=None):
        if type(obj) == dict:
            obj = Struct(**obj)
        self._obj = obj # the actual object wrapped
        if id is None:
            id = base64.urlsafe_b64encode(name) # tied to the name
        if app_label is None:
            app_label = '-'

        self._name = name
        self._app_label = app_label
        self._id = id

        # construct the object-identifier its format is:
        # <app_label>%<name>%<pk>
        object_identifier = str(app_label)+'%'+str(name)+'%'+str(id)
        self._object_identifier = object_identifier

        redis_connection = redis.Redis(connection_pool=redis_pool)
        
        # the channellist is a redis `set` that contains all channels
        # bound to unique client sessions.
        channellist = redis_connection.smembers(
            settings.REDIS_KEY_CHANNELLIST) or []
        for channel in channellist:
            # each client session (channel) has a redis `set` containing
            # object identifiers to keep watch of and update when
            # values change -> whatchlist
            redis_connection.sadd(
                settings.REDIS_KEY_PREFIX_WATCHLIST+channel,
                object_identifier)

    def __getattribute__(self, name):
        '''
        Wrap all attributes retrieved in comments containing this
        object_identifier.
        TODO: Handle relationships.
        '''
        # dirty hack
        if name in ['set_changed', '__dict__', 'skip_fields']:
            return object.__getattribute__(self, name)
        
        attr = getattr(object.__getattribute__(self, "_obj"), name)

        if name in self.skip_fields:
            return attr
        
        object_identifier = object.__getattribute__(
            self,
            "_object_identifier"
        )
        ostr = '<!--%s-->' % (object_identifier + '%' + name)
        cstr = '<!--/%s-->' % (object_identifier + '%' + name)
        return SafeString(ostr + str(attr) + cstr)

    def set_changed(self):
        obj = object.__getattribute__(self, '_obj')
        name = object.__getattribute__(self, '_name')
        app_label = object.__getattribute__(self, '_app_label')
        id = object.__getattribute__(self, '_id')
        RTObservable.emit_change(
            name, obj, app_label, id
        )
        return self
        
    @classmethod
    def emit_change(cls, name, obj, app_label=None, id=None):
        if isinstance(obj, Struct):
            obj = obj.__dict__
        if id is None:
            id = base64.urlsafe_b64encode(name) # tied to the name
        if app_label is None:
            app_label = '-'
        
        redis_connection = redis.Redis(connection_pool=redis_pool)
        
        channellist = redis_connection.smembers(
            settings.REDIS_KEY_CHANNELLIST) or []

        if str(id) != 'Q':
            for channel in channellist:
                watchlist = redis_connection.smembers(
                    settings.REDIS_KEY_PREFIX_WATCHLIST+channel) or []
                for descriptor in watchlist:
                    _app_label, _name, _pk = descriptor.split("%")
                    if all([
                        _app_label == app_label,
                        _name == name,
                        _pk == str(id)
                    ]):
                        redis_connection.rpush(
                            channel,
                            json.dumps({descriptor:obj}, cls=RTEncoder))
        else:
            # this is a query, somehow we need to
            # find out which client-side event to
            # emit and send
            # {emit:event_id}
            # to the client
            eventids = redis_connection.smembers(
                (
                    app_label +
                    '%' +
                    name +
                    '%Q'
                ))
            for channel in channellist:
                for event_id in eventids:
                    redis_connection.rpush(
                        channel,
                        json.dumps({'emit':event_id})
                    )


class RTQueryProxy(RTObservable):
    '''
    a proxy for QuerySet instances.
    '''
    def __init__(self, qs):
        ct = ContentType.objects.get_for_model(qs.model)
        setattr(qs, '__content', '') # this is a wrapper event
        super(RTQueryProxy, self).__init__(
            ct.model,
            {},
            ct.app_label,
            'Q',
        )

    @classmethod
    def emit_change(cls, obj):
        ct = ContentType.objects.get_for_model(obj)
        RTObservable.emit_change(
            ct.model, {}, ct.app_label, 'Q')
        

                    
class RTModelProxy(RTObservable):
    '''
    A proxy for Model instances. After inspecting the template context
    any Model instance will be wrapped in an instance of RTModelProxy.
    The proxy does no modifications to the Model or data it wraps any
    attribute retrieved into a string:
        "<!--`object-identifier`-->`original`<!--/`object-identifier`-->
    so the client side script can relocate and modify its value when
    database entries change.
    '''

    skip_fields = ('id', 'pk')
    
    def __init__(self, obj):
        ct = ContentType.objects.get_for_model(obj)
        super(RTModelProxy, self).__init__(
            ct.model,
            obj,
            ct.app_label,
            obj.pk
        )

    @classmethod
    def emit_change(cls, obj):
        ct = ContentType.objects.get_for_model(obj)
        RTObservable.emit_change(
            ct.model, model_to_dict(obj),
            ct.app_label, obj.pk
        )

class RTTemplateResponse(TemplateResponse):
    '''
    A TemplateResponse subclass to inspect the context and wrap all
    model instances into `RTModelProxy` instances.
    '''
    
    def __init__(self, *args, **kwargs):
        target_query = kwargs.pop('target_query', None)
        if not target_query is None:
            kwargs.update({'content_type': 'application/json'})
        super(RTTemplateResponse, self).__init__(*args, **kwargs)
        self.target_query = target_query
        self.wrapping_events = []

    def process_wrapping_events(self, content):
        cnt = content or ''
        for e in self.wrapping_events:
            object.__getattribute__(e, '_obj').__content = cnt
            cnt = e.__content
        return cnt
                    
    def render(self):
        resp = super(RTTemplateResponse, self).render()
        if not self.target_query is None:
            resp.content = json.dumps(dict(
                target_query=self.target_query,
                body=self.process_wrapping_events(resp.content)
            ))
        return resp
        
    def resolve_context(self, context):
        '''
        Main entry point to inspect the context.
        Calls `self.adapt_list_or_dict(1)`
        '''
        context = self.adapt_list_or_dict(context)
        return super(RTTemplateResponse, self).resolve_context(context)
    
    def adapt_list_or_dict(self, list_or_dict):
        '''
        Inspects a list or dict and passes its contents
        either to `self.adapt_query(1)`, `self.adapt_model(1)`
        or recursively to `self.adapt_list_or_dict(1)`.
        '''
        
        # test a value and pass it on
        def test_v(vv):
            if type(vv) == dict or type(vv) == list:
                vv = self.adapt_list_or_dict(vv)
            elif isinstance(vv, QuerySet):
                vv = self.adapt_query(vv)
            elif isinstance(vv, Model):
                vv = self.adapt_model(vv)
            return vv
        
        # iterate based on type
        result = None
        if type(list_or_dict) == dict:
            result = {}
            for k,v in list_or_dict.iteritems():
                result[k] = test_v(v)
        elif type(list_or_dict) == list:
            result = []
            for v in list_or_dict:
                result.append(test_v(v))
        
        return result
    
    def adapt_model(self, model):
        return RTModelProxy(model)
    
    def adapt_query(self, query):
        result = []
        for model in query:
            result.append(self.adapt_model(model))
        self.wrapping_events.append(RTQueryProxy(query))
        return result


class RTView(TemplateView):
    '''
    The main TemplateView subclass which enables realtime web.
    
      `RTView.event(2)`    - decorater to define client side
                             event handling
      `self.dispatch(1+)`  - entry point to handle client side
                             emitted events through AJAX
    
    Howto Use
    =========
    
    TBD
    
    '''
    
    events = {}
    '''
    keep track of decorated event methods
    '''
    
    response_class = RTTemplateResponse
    '''
    TemplateResponse class attribute see Django docs
    '''
    
    def dispatch(self, request, *args, **kwargs):
        '''
        Main entry point for all http methods on this view.
        No need to override this method.
        TODO: Graceful error handling
        '''
        if all([
            request.is_ajax(),
            request.method == 'POST',
            HTTP_X_EVENT_ID in request.META
        ]):
            request_data = {}
            request_data.update(request.POST)
            kwargs = {}
            
            # turn key values into str and 'unlist' entries
            for k,v in request_data.iteritems():
                if type(v) == list and len(v) == 1:
                    v = v[0]
                kwargs[str(k)] = v
                
            # retrieve the decorated function
            try:
                handler_info =  self.__class__.events[
                    request.META[HTTP_X_EVENT_ID]]
            except KeyError:
                raise Exception('Could not locate event %s in my dict %s' % (
                    request.META[HTTP_X_EVENT_ID],
                    str(self.__class__.events)
                ))
            
            # handler_info is a tuple (instance, function)
            
            try:
                # call the decorated function
                response = handler_info[1](
                    handler_info[0], request, **kwargs)
            
            except:
                if settings.DEBUG:
                    strbuf = StringIO.StringIO()
                    traceback.print_exc(50, strbuf)
                    response = HttpResponse('Error:\n' + strbuf.getvalue())
                else:
                    raise
            return response
        
        def inject_javascript(resp):
            # inject required javascripts
                
            pos = resp.content.find('</head>')
            if pos != -1:
                resp.content = resp.content[:pos] + (
                    RT_SCRIPT % reverse('application_js')
                ) + resp.content[pos:]
        
        response = super(RTView, self).dispatch(request, *args, **kwargs)
        if not response is None and hasattr(
            response, 'add_post_render_callback'):
            response.add_post_render_callback(inject_javascript)
        
        return response
        
    
    @classmethod
    def compute_event_id(cls, func, name, query):
        '''
        Returns the event id for a given function object, event name and
        jquery string.
        '''
        return quote(
            base64.urlsafe_b64encode(func.func_name)+str(name)+str(query))


    @classmethod
    def empty_response(cls):
        return HttpResponse('')
    
        
    @classmethod
    def event(cls, name, query):
        '''
        Decorator for registering client side events.
        
            - `name` the client side event name e.g. "click"
            - `query` a jQuery std query string e.g. "#mybutton"
            
        The function that is being decorated defines keyword arguments
        wich will be populated with the client side data defined by
        jQuery std query strings in their default value. The following
        example expects the value of an input field when a button is clicked:
        
            @RTView.event("click", "#mybutton")
            def on_mybutton_click(self, request, thevalue="#myinput" ):
                return RTResponse('#mydiv', 'Clicked, value=' + thevalue)
        '''
        
        def decorator(func):
            (args, varargs, keywords, defaults) = getargspec(func)
            event_id = cls.compute_event_id(func, name, query)
            
            self_ = args[0] # the instance
            args = args[2:] # strip self, request

            argsndefaults = {}
            if len(args) > 0 and len(args) == len(defaults):
                argsndefaults = dict(zip(args, defaults))
            
            # do not allow duplicates
            if event_id in cls.events:
                raise Exception('Event seems already registered? %s' % str(
                    cls.events[event_id]))
            
            @wraps(func)
            def pass_event_id(self_, request, **kwargs):
                response = func(self_, request, **kwargs)
                redis_connection = redis.Redis(
                    connection_pool=redis_pool)

                def callback(resp):
                    for e in resp.wrapping_events:
                        name = object.__getattribute__(e, '_name')
                        app_label = object.__getattribute__(e, '_app_label')
                        id = object.__getattribute__(e, '_id')
                        redis_connection.sadd(
                            (
                                app_label +
                                '%' +
                                name +
                                '%' +
                                id
                            ),
                            event_id,
                        )

                if not response is None and hasattr(
                    response, 'add_post_render_callback'):
                    response.add_post_render_callback(callback)
                
                return response

            # register the event
            cls.events[event_id] = (
                self_, pass_event_id, name, query, argsndefaults )

            return pass_event_id

        return decorator


class RTJavascriptEvents(TemplateView):
    '''
    Dynamic javascript response responsible for all client side interaction.
    
    Any RTView generated response gets this script injected.
    
    The template passes the channel name and registered events to the client.
    '''
    
    template_name = 'application.js'
    content_type = 'application/javascript'
    
    def get_context_data(self, **kwargs):
        context = super(RTJavascriptEvents, self).get_context_data(**kwargs)
        events = [] # will contain a list of dictionaries
        
        # collect subclasses of RTView
        subclasses = itersubclasses(RTView)
        
        # collect all registered events in all subclasses
        for klass in subclasses:
            events.append(dict(
                [(SafeString(i), v) for i,v in klass.events.iteritems()]))
        
        context['events'] = events
        
        # get the channel name from the session or generate a new one
        channel_name = self.request.session.get('channel_name', None)
        if not channel_name:
            channel_name = uuid4().hex
            self.request.session['channel_name'] = channel_name
        
        context['channel'] = channel_name
        
        redis_connection = redis.Redis(connection_pool=redis_pool)
        
        # add the channel name to the channellist redis `set`
        redis_connection.sadd(settings.REDIS_KEY_CHANNELLIST, channel_name)
        
        # push an initiator message to the channel
        redis_connection.rpush(channel_name, '{message:"HI"}');
        
        return context


class RTManagement(TemplateView):
    template_name = 'management.html'
    
    def get_context_data(self, **kwargs):
        redis_connection = redis.Redis(connection_pool=redis_pool)
        context = super(RTManagement, self).get_context_data(**kwargs)
        
        queues = {}
        for channel_name in redis_connection.smembers(
            settings.REDIS_KEY_CHANNELLIST
        ):
            watchnevent = [[],[]]
            watchnevent[0] = redis_connection.smembers(
                settings.REDIS_KEY_PREFIX_WATCHLIST+channel_name)
            #for descriptor in watchnevent[0]:
            #    watchnevent[1] = redis_connection.smembers(descriptor)
            queues[channel_name] = watchnevent
        
        context['watchlist'] = queues
        
        return context