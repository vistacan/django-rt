from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

import redis

from views import RTModelProxy

redis_pool = redis.ConnectionPool()


@receiver(post_save)
def on_post_save(sender, instance, signal, created, **kwargs):
    RTModelProxy.emit_change(instance)


class Test(models.Model):
    name = models.CharField(max_length=128)