from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("events/", views.EventListView.as_view(), name="events"),
    path("events/<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("events/<int:pk>/apply/", views.ApplyView.as_view(), name="apply"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("applications/", views.MyApplicationsView.as_view(), name="my_applications"),
    path("manage/", views.ManageView.as_view(), name="manage"),
    path("manage/applications/<int:pk>/next/", views.NextStatusView.as_view(), name="next_status"),
]
