from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.safestring import SafeString

import redis
import json


redis_pool = redis.ConnectionPool()


@receiver(post_save)
def on_post_save(sender, instance, signal, created, **kwargs):
    redis_connection = redis.Redis(connection_pool=redis_pool)
    channellist = redis_connection.smembers(
        settings.REDIS_KEY_CHANNELLIST) or []
    for channel in channellist:
        watchlist = redis_connection.smembers(
            settings.REDIS_KEY_PREFIX_WATCHLIST+channel) or []
        for descriptor in watchlist:
            app_label, name, pk = descriptor.split("%")
            ct = ContentType.objects.get_for_model(instance)
            if all([
                ct.app_label == app_label,
                ct.name == name, str(instance.pk) == pk
            ]):
                redis_connection.rpush(
                    channel,
                    json.dumps({descriptor:model_to_dict(instance)}))
    

class RTModelProxy(object):
    '''
    A proxy for Model instances. After inspecting the template context
    any Model instance will be wrapped in an instance of RTModelProxy.
    The proxy does no modifications to the Model or data it wraps any
    attribute retrieved into a string:
        "<!--`object-identifier`-->`original`<!--/`object-identifier`-->
    so the client side script can relocate and modify its value when
    database entries change.
    '''
    
    def __init__(self, obj):
        self._obj = obj # the model instance wrapped
        ct = ContentType.objects.get_for_model(obj)
        
        # construct the object-identifier its format is:
        # <app_label>%<name>%<pk>
        object_identifier = ct.app_label+'%'+ct.model+'%'+str(obj.pk)
        self._object_identifier = object_identifier
        
        redis_connection = redis.Redis(connection_pool=redis_pool)
        
        # the channellist is a redis `set` that contains all channels
        # bound to unique client sessions.
        channellist = redis_connection.smembers(
            settings.REDIS_KEY_CHANNELLIST) or []
        for channel in channellist:
            # each client session (channel) has a redis `set` containing
            # object identifiers to keep watch of and update when database
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
        attr = getattr(object.__getattribute__(self, "_obj"), name)
        object_identifier = object.__getattribute__(
            self,
            "_object_identifier"
        )
        ostr = '<!--%s-->' % (object_identifier + '%' + name)
        cstr = '<!--/%s-->' % (object_identifier + '%' + name)
        return SafeString(ostr + attr + cstr)


class Test(models.Model):
    name = models.CharField(max_length=128)