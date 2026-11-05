from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

ADMIN_GROUP = "Администраторы"


def is_admin(user):
    """Администратор это пользователь из группы «Администраторы»."""
    return user.is_authenticated and user.groups.filter(name=ADMIN_GROUP).exists()


class AdminRequiredMixin(LoginRequiredMixin):
    """Гость уходит на страницу входа, участник получает 403."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ParticipantRequiredMixin(LoginRequiredMixin):
    """Заявки подаёт и смотрит только участник; администратор ведёт заявки в панели."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
