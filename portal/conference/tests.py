from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationForm, RegisterForm, normalize_phone
from .models import Application, Event, Profile, Status


def make_user(name, group="Участники", password="Proverka-2026"):
    user = User.objects.create_user(name, name + "@example.com", password)
    user.groups.add(Group.objects.get(name=group))
    Profile.objects.create(user=user, phone="+79160000001")
    return user


def make_event(days=10, title="Тестовое мероприятие"):
    return Event.objects.create(title=title, description="Описание", city="Москва", place="Зал",
                                starts_at=timezone.now() + timedelta(days=days))


class RegisterFormTests(TestCase):
    data = {"username": "elya_t", "email": "elya@example.com", "phone": "+7 916 123-45-67",
            "password1": "Proverka-2026", "password2": "Proverka-2026"}

    def test_valid(self):
        self.assertTrue(RegisterForm(self.data).is_valid())

    def test_username_too_short(self):
        self.assertIn("username", RegisterForm({**self.data, "username": "ab"}).errors)

    def test_username_bad_chars(self):
        self.assertIn("username", RegisterForm({**self.data, "username": "elya t"}).errors)

    def test_username_taken(self):
        make_user("elya_t")
        self.assertIn("username", RegisterForm(self.data).errors)

    def test_phone_normalized(self):
        self.assertEqual(normalize_phone("8 (900) 123-45-67"), "+79001234567")
        form = RegisterForm({**self.data, "phone": "8 (900) 123-45-67"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["phone"], "+79001234567")

    def test_phone_wrong(self):
        for bad in ["12345", "+7 916 abc-45-67", "+1 202 555 0100"]:
            self.assertIn("phone", RegisterForm({**self.data, "phone": bad}).errors, bad)

    def test_email_wrong(self):
        self.assertIn("email", RegisterForm({**self.data, "email": "elya"}).errors)

    def test_password_short_and_mismatch(self):
        self.assertIn("password1", RegisterForm({**self.data, "password1": "Ab1", "password2": "Ab1"}).errors)
        self.assertIn("password2", RegisterForm({**self.data, "password2": "Drugoj-2026"}).errors)

    def test_save_creates_user_profile_group(self):
        form = RegisterForm(self.data)
        form.is_valid()
        user = form.save()
        self.assertEqual(user.profile.phone, "+79161234567")
        self.assertTrue(user.groups.filter(name="Участники").exists())


class ApplicationFormTests(TestCase):
    def test_past_event_rejected(self):
        user, event = make_user("anna"), make_event(days=-1)
        form = ApplicationForm({"room": "Большой зал", "payment": "Банковская карта"}, user=user, event=event)
        self.assertFalse(form.is_valid())

    def test_second_application_rejected(self):
        user, event = make_user("anna"), make_event()
        data = {"room": "Большой зал", "payment": "Банковская карта"}
        first = ApplicationForm(data, user=user, event=event)
        self.assertTrue(first.is_valid())
        first.save()
        self.assertFalse(ApplicationForm(data, user=user, event=event).is_valid())

    def test_new_application_has_status_new(self):
        user, event = make_user("anna"), make_event()
        form = ApplicationForm({"room": "Большой зал", "payment": "Банковская карта"}, user=user, event=event)
        form.is_valid()
        self.assertEqual(form.save().status.name, "новая")


class AccessTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", "Администраторы")
        self.user = make_user("anna")
        self.other = make_user("petr")
        self.event = make_event()
        self.app = Application.objects.create(user=self.other, event=self.event, status=Status.objects.get(name="новая"),
                                              room="Большой зал", payment="Банковская карта")

    def test_guest_redirected_to_login(self):
        for name in ("manage", "my_applications"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse("login"), r["Location"])

    def test_guest_cannot_apply(self):
        r = self.client.get(reverse("apply", args=[self.event.pk]))
        self.assertEqual(r.status_code, 302)

    def test_participant_has_no_access_to_panel(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("manage")).status_code, 403)
        r = self.client.post(reverse("next_status", args=[self.app.pk]))
        self.assertEqual(r.status_code, 403)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status.name, "новая")

    def test_admin_changes_status(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("manage")).status_code, 200)
        self.client.post(reverse("next_status", args=[self.app.pk]))
        self.app.refresh_from_db()
        self.assertEqual(self.app.status.name, "назначено")

    def test_participant_sees_only_own_applications(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("my_applications"))
        self.assertEqual(len(r.context["applications"]), 0)
        self.client.force_login(self.other)
        self.assertEqual(len(self.client.get(reverse("my_applications")).context["applications"]), 1)


class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("anna")

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"])
    def test_password_is_hashed(self):
        user = User.objects.create_user("hash_user", "h@example.com", "Proverka-2026")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertNotIn("Proverka-2026", user.password)

    def test_sql_injection_in_login(self):
        r = self.client.post(reverse("login"), {"username": "' OR '1'='1", "password": "' OR '1'='1"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sql_injection_in_search(self):
        make_event(title="Обычное")
        r = self.client.get(reverse("events"), {"q": "' OR 1=1 --"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context["events"]), 0)

    def test_lockout_after_five_wrong_passwords(self):
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "anna", "password": "wrong-password"})
        r = self.client.post(reverse("login"), {"username": "anna", "password": "Proverka-2026"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(r, "Слишком много неудачных попыток")

    def test_good_login_resets_counter(self):
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "anna", "password": "wrong-password"})
        self.client.post(reverse("login"), {"username": "anna", "password": "Proverka-2026"})
        self.client.logout()
        for _ in range(3):
            self.client.post(reverse("login"), {"username": "anna", "password": "wrong-password"})
        r = self.client.post(reverse("login"), {"username": "anna", "password": "Proverka-2026"})
        self.assertEqual(r.status_code, 302)

    def test_csrf_token_required(self):
        strict = Client(enforce_csrf_checks=True)
        r = strict.post(reverse("login"), {"username": "anna", "password": "Proverka-2026"})
        self.assertEqual(r.status_code, 403)

    def test_session_cookie_flags(self):
        r = self.client.post(reverse("login"), {"username": "anna", "password": "Proverka-2026"})
        cookie = r.cookies["sessionid"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_html_in_comment_is_escaped(self):
        admin = make_user("boss", "Администраторы")
        Application.objects.create(user=self.user, event=make_event(), status=Status.objects.get(name="новая"),
                                   room="Зал", payment="Карта", comment="<script>alert(1)</script>")
        self.client.force_login(admin)
        r = self.client.get(reverse("manage"))
        self.assertNotContains(r, "<script>alert(1)</script>")
