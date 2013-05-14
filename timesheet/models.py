from django.db import models
from django.contrib.auth.models import User

import datetime


class Entry(models.Model):
    author = models.ForeignKey(User)
    date = models.DateField(default=lambda:datetime.datetime.now().date())
    hours = models.DecimalField(
        max_digits=4, decimal_places=2, default=0.00)
    declared = models.BooleanField(default=False)
    description = models.CharField(max_length=65)