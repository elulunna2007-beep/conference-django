import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, User
from django.core.validators import RegexValidator

from .models import Application, Profile, Status


def normalize_phone(raw):
    """Приводит телефон к виду +7XXXXXXXXXX: убирает пробелы, скобки, дефисы, 8 в начале заменяет на +7."""
    phone = re.sub(r"[\s()\-]", "", raw)
    if phone.startswith("8"):
        phone = "+7" + phone[1:]
    return phone


class RegisterForm(forms.Form):
    username = forms.CharField(
        label="Логин", min_length=3, max_length=20,
        validators=[RegexValidator(r"^[A-Za-z0-9_]+$", "Только латиница, цифры и знак «_».")])
    email = forms.EmailField(label="Почта")
    phone = forms.CharField(label="Телефон", max_length=20, help_text="Например, +7 916 123-45-67")
    password1 = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Пароль ещё раз", strip=False, widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Такой логин уже занят.")
        return username

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if not re.fullmatch(r"\+7\d{10}", phone):
            raise forms.ValidationError("Телефон должен быть в формате +7XXXXXXXXXX.")
        return phone

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        password_validation.validate_password(password)
        return password

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password2") and data["password1"] != data["password2"]:
            self.add_error("password2", "Пароли не совпадают.")
        return data

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(d["username"], d["email"], d["password1"])
        Profile.objects.create(user=user, phone=d["phone"])
        user.groups.add(Group.objects.get(name="Участники"))
        return user


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["room", "payment", "comment"]

    def __init__(self, *args, user=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.event = event

    def clean(self):
        data = super().clean()
        if self.event.is_finished():
            raise forms.ValidationError("Мероприятие уже прошло, заявку подать нельзя.")
        if Application.objects.filter(user=self.user, event=self.event).exists():
            raise forms.ValidationError("Вы уже подали заявку на это мероприятие.")
        return data

    def save(self, commit=True):
        app = super().save(commit=False)
        app.user = self.user
        app.event = self.event
        app.status = Status.objects.get(name="новая")
        if commit:
            app.save()
        return app
