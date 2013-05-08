from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.forms.models import model_to_dict

from views import RTModelProxy
import redis
import json


redis_pool = redis.ConnectionPool()


@receiver(post_save)
def on_post_save(sender, instance, signal, created, **kwargs):
    redis_connection = redis.Redis(connection_pool=redis_pool)
    channellist = redis_connection.smembers(settings.REDIS_KEY_CHANNELLIST) or []
    for channel in channellist:
        watchlist = redis_connection.smembers(settings.REDIS_KEY_PREFIX_WATCHLIST+channel) or []
        for descriptor in watchlist:
            app_label, name, pk = descriptor.split("%")
            ct = ContentType.objects.get_for_model(instance)
            if all([ct.app_label == app_label, ct.name == name, str(instance.pk) == pk]):
                redis_connection.rpush(channel, json.dumps({descriptor:model_to_dict(instance)}))
    

class Test(models.Model):
    name = models.CharField(max_length=128)