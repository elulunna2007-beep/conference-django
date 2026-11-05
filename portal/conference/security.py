import hashlib

from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError

MAX_TRIES = 5      # столько неверных паролей подряд можно ввести
WINDOW = 300       # секунд, потом счётчик сбрасывается


def _key(username):
    return "login-fails:" + hashlib.sha256(username.lower().encode()).hexdigest()[:24]


def is_blocked(username):
    return cache.get(_key(username), 0) >= MAX_TRIES


def add_fail(username):
    cache.set(_key(username), cache.get(_key(username), 0) + 1, WINDOW)


def reset(username):
    cache.delete(_key(username))


class LoginForm(AuthenticationForm):
    """Обычная форма входа плюс защита от подбора пароля."""

    def clean(self):
        username = self.cleaned_data.get("username", "")
        if username and is_blocked(username):
            raise ValidationError("Слишком много неудачных попыток. Подождите 5 минут и попробуйте снова.", code="blocked")
        try:
            data = super().clean()
        except ValidationError:
            if username:
                add_fail(username)
            raise
        reset(username)
        return data
