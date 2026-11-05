from django.contrib.auth import views as auth_views
from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView

from . import views
from .security import LoginForm

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("favicon.ico", RedirectView.as_view(url=static("img/favicon.svg"), permanent=True)),
    path("events/", views.EventListView.as_view(), name="events"),
    path("events/<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("events/<int:pk>/apply/", views.ApplyView.as_view(), name="apply"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html", authentication_form=LoginForm, redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("applications/", views.MyApplicationsView.as_view(), name="my_applications"),
    path("applications/<int:pk>/review/", views.ReviewCreateView.as_view(), name="review"),
    path("applications/<int:pk>/cancel/", views.CancelApplicationView.as_view(), name="cancel_application"),
    path("manage/", views.ManageView.as_view(), name="manage"),
    path("manage/events/", views.ManageEventsView.as_view(), name="manage_events"),
    path("manage/events/new/", views.EventCreateView.as_view(), name="event_create"),
    path("manage/events/<int:pk>/edit/", views.EventUpdateView.as_view(), name="event_edit"),
    path("manage/events/<int:pk>/delete/", views.EventDeleteView.as_view(), name="event_delete"),
    path("manage/applications/<int:pk>/next/", views.NextStatusView.as_view(), name="next_status"),
]
