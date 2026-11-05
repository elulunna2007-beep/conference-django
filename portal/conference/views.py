from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import ApplicationForm, EventForm, RegisterForm, ReviewForm
from .models import Application, Event, Review, Status
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
        city = self.request.GET.get("city", "")
        if q:
            events = events.filter(title__icontains=q)
        if city:
            events = events.filter(city=city)
        return events

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["city"] = self.request.GET.get("city", "")
        ctx["cities"] = Event.objects.order_by("city").values_list("city", flat=True).distinct()
        return ctx


class EventDetailView(DetailView):
    model = Event
    template_name = "event_detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["reviews"] = Review.objects.filter(application__event=self.object).select_related("application__user")
        return ctx


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
        apps = Application.objects.select_related("event", "status", "user")
        status = self.request.GET.get("status", "")
        event = self.request.GET.get("event", "")
        if status.isdigit():
            apps = apps.filter(status_id=int(status))
        if event.isdigit():
            apps = apps.filter(event_id=int(event))
        return apps

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = Status.objects.all()
        ctx["events"] = Event.objects.all()
        ctx["status"] = self.request.GET.get("status", "")
        ctx["event"] = self.request.GET.get("event", "")
        return ctx


class NextStatusView(AdminRequiredMixin, View):
    def post(self, request, pk):
        app = get_object_or_404(Application, pk=pk)
        following = app.advance()
        if following:
            messages.success(request, "Статус заявки изменён: %s." % following.name)
        return redirect("manage")


class ReviewCreateView(ParticipantRequiredMixin, CreateView):
    """Отзыв на свою заявку: только после завершения заявки и самого мероприятия."""
    template_name = "review_form.html"
    form_class = ReviewForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.application = get_object_or_404(Application, pk=kwargs["pk"], user=request.user)
            if not self.application.can_review():
                messages.error(request, "Отзыв можно оставить после завершения заявки и проведения мероприятия.")
                return redirect("my_applications")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["application"] = self.application
        return ctx

    def form_valid(self, form):
        review = form.save(commit=False)
        review.application = self.application
        review.save()
        messages.success(self.request, "Спасибо, отзыв сохранён.")
        return redirect("my_applications")


class CancelApplicationView(ParticipantRequiredMixin, View):
    """Участник может отозвать свою заявку, пока она новая."""

    def post(self, request, pk):
        app = get_object_or_404(Application, pk=pk, user=request.user)
        if app.status.position == 1:
            app.delete()
            messages.success(request, "Заявка отменена.")
        else:
            messages.error(request, "Заявку уже взяли в работу, отменить её нельзя.")
        return redirect("my_applications")


class ManageEventsView(AdminRequiredMixin, ListView):
    template_name = "manage_events.html"
    context_object_name = "events"

    def get_queryset(self):
        return Event.objects.all().order_by("-starts_at")


class EventCreateView(AdminRequiredMixin, CreateView):
    template_name = "event_form.html"
    form_class = EventForm
    success_url = reverse_lazy("manage_events")

    def form_valid(self, form):
        messages.success(self.request, "Мероприятие добавлено.")
        return super().form_valid(form)


class EventUpdateView(AdminRequiredMixin, UpdateView):
    model = Event
    template_name = "event_form.html"
    form_class = EventForm
    success_url = reverse_lazy("manage_events")

    def form_valid(self, form):
        messages.success(self.request, "Изменения сохранены.")
        return super().form_valid(form)


class EventDeleteView(AdminRequiredMixin, DeleteView):
    model = Event
    template_name = "event_confirm_delete.html"
    success_url = reverse_lazy("manage_events")

    def form_valid(self, form):
        messages.success(self.request, "Мероприятие удалено вместе с заявками на него.")
        return super().form_valid(form)
