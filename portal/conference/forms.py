import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, User
from django.core.validators import RegexValidator

from .models import Application, Event, Profile, Review, Status


def normalize_phone(raw):
    """Приводит телефон к виду +7XXXXXXXXXX: убирает пробелы, скобки, дефисы, 8 в начале заменяет на +7."""
    phone = re.sub(r"[\s()\-]", "", raw)
    if phone.startswith("8"):
        phone = "+7" + phone[1:]
    return phone


class RegisterForm(forms.Form):
    # атрибуты в widget это проверка в браузере, правила на сервере те же
    username = forms.CharField(
        label="Логин", min_length=3, max_length=20,
        validators=[RegexValidator(r"^[A-Za-z0-9_]+$", "Только латиница, цифры и знак «_».")],
        widget=forms.TextInput(attrs={"pattern": "[A-Za-z0-9_]+", "title": "Латиница, цифры и знак _", "autocomplete": "username"}))
    email = forms.EmailField(label="Почта", max_length=254)
    phone = forms.CharField(
        label="Телефон", max_length=20, help_text="Например, +7 916 123-45-67",
        widget=forms.TextInput(attrs={"type": "tel", "pattern": r"(\+7|8)[\d\s()\-]{10,14}", "title": "Формат +7 916 123-45-67"}))
    password1 = forms.CharField(label="Пароль", strip=False, widget=forms.PasswordInput(attrs={"minlength": 8, "autocomplete": "new-password"}))
    password2 = forms.CharField(label="Пароль ещё раз", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_username(self):
        username = self.cleaned_data["username"]
        # логин считаем занятым и в другом регистре: Admin и admin это один логин
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Такой логин уже занят.")
        return username

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if not re.fullmatch(r"\+7\d{10}", phone):
            raise forms.ValidationError("Телефон должен быть в формате +7XXXXXXXXXX.")
        return phone

    def clean(self):
        data = super().clean()
        password = data.get("password1")
        if password:
            if not password.strip():
                self.add_error("password1", "Пароль не может состоять из одних пробелов.")
            else:
                # пользователя передаём, чтобы пароль не мог совпадать с логином или почтой
                user = User(username=data.get("username", ""), email=data.get("email", ""))
                try:
                    password_validation.validate_password(password, user)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        if password and data.get("password2") and password != data["password2"]:
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


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "text"]
        labels = {"text": "Ваш отзыв"}
        widgets = {"text": forms.Textarea(attrs={"rows": 4, "maxlength": 500})}

    # оценка только от 1 до 5: список в браузере не защищает, если отправить значение мимо формы
    rating = forms.IntegerField(label="Оценка", min_value=1, max_value=5,
                                widget=forms.Select(choices=[(i, "%d из 5" % i) for i in range(5, 0, -1)]))

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 10:
            raise forms.ValidationError("Напишите хотя бы 10 символов.")
        return text


class EventForm(forms.ModelForm):
    """Форма мероприятия в панели администратора."""
    starts_at = forms.DateTimeField(
        label="Дата и время", input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))
    image = forms.ChoiceField(label="Фото", required=False,
                              choices=[("", "Без фото")] + [("event-%d.jpg" % i, "Фото %d" % i) for i in range(1, 10)])

    class Meta:
        model = Event
        fields = ["title", "description", "starts_at", "city", "place", "image"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Название не короче 5 символов.")
        return title
