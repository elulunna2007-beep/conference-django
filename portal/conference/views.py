from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from .forms import ApplicationForm, RegisterForm
from .models import Application, Event, Status
from .permissions import AdminRequiredMixin, ParticipantRequiredMixin


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["events"] = Event.objects.filter(starts_at__gte=timezone.now())[:3]
        return ctx


class EventListView(ListView):
    template_name = "events.html"
    context_object_name = "events"

    def get_queryset(self):
        events = Event.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            events = events.filter(title__icontains=q)
        return events

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class EventDetailView(DetailView):
    model = Event
    template_name = "event_detail.html"
    context_object_name = "event"


class RegisterView(FormView):
    template_name = "register.html"
    form_class = RegisterForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Вы зарегистрированы и вошли в систему.")
        return redirect("home")


class ApplyView(ParticipantRequiredMixin, CreateView):
    template_name = "apply.html"
    form_class = ApplicationForm

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, event=self.event)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["event"] = self.event
        return ctx

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Заявка отправлена.")
        return redirect("my_applications")


class MyApplicationsView(ParticipantRequiredMixin, ListView):
    template_name = "my_applications.html"
    context_object_name = "applications"

    def get_queryset(self):
        return Application.objects.filter(user=self.request.user).select_related("event", "status")


class ManageView(AdminRequiredMixin, ListView):
    """Панель администратора: все заявки и смена статуса."""
    template_name = "manage.html"
    context_object_name = "applications"

    def get_queryset(self):
        return Application.objects.select_related("event", "status", "user")


class NextStatusView(AdminRequiredMixin, View):
    def post(self, request, pk):
        app = get_object_or_404(Application, pk=pk)
        following = Status.objects.filter(position__gt=app.status.position).first()
        if following:
            app.status = following
            app.save()
            messages.success(request, "Статус заявки изменён: %s." % following.name)
        return redirect("manage")
