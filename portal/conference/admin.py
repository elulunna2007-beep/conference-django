from django.contrib import admin

from .models import Application, Event, Profile, Review, Status

admin.site.register([Application, Event, Profile, Review, Status])
