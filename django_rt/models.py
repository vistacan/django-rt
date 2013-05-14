from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

import redis

from views import RTModelProxy, RTQueryProxy

redis_pool = redis.ConnectionPool()


@receiver(post_save)
def on_post_save(sender, instance, signal, created, **kwargs):
    if not created:
        RTModelProxy.emit_change(instance)
    else:
        # TODO:keep track of query result length
        RTQueryProxy.emit_change(instance)


@receiver(post_delete)
def on_post_delete(sender, instance, using, **kwargs):
    # TODO:keep track of query result length    
    RTQueryProxy.emit_change(instance)


class Test(models.Model):
    name = models.CharField(max_length=128)

class Test2(models.Model):
    name = models.CharField(max_length=128)