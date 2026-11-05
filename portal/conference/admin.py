from django.contrib import admin

from .models import Application, Event, Profile, Review, Status


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "starts_at"]
    list_filter = ["city"]
    search_fields = ["title"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["user", "event", "status", "created_at"]
    list_filter = ["status", "event"]


admin.site.register([Profile, Review, Status])
