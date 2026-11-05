from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationForm, RegisterForm, normalize_phone
from .models import Application, Event, Profile, Review, Status


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


class ReviewAndFilterTests(TestCase):
    def setUp(self):
        self.user = make_user("anna")
        self.other = make_user("petr")
        self.admin = make_user("boss", "Администраторы")
        self.past = make_event(days=-3, title="Прошедшее")
        self.future = make_event(days=5, title="Будущее")
        self.new, self.assigned, self.done = [Status.objects.get(name=n) for n in ("новая", "назначено", "завершено")]

    def app(self, event, status, user=None):
        return Application.objects.create(user=user or self.user, event=event, status=status, room="Малый зал", payment="Банковская карта")

    def test_cannot_review_not_completed(self):
        a = self.app(self.past, self.assigned)
        self.client.force_login(self.user)
        r = self.client.get(reverse("review", args=[a.pk]))
        self.assertRedirects(r, reverse("my_applications"))

    def test_cannot_review_before_event(self):
        a = self.app(self.future, self.done)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("review", args=[a.pk])), reverse("my_applications"))

    def test_review_saved_after_completion(self):
        a = self.app(self.past, self.done)
        self.client.force_login(self.user)
        r = self.client.post(reverse("review", args=[a.pk]), {"rating": 5, "text": "Очень полезная встреча"})
        self.assertRedirects(r, reverse("my_applications"))
        self.assertEqual(a.review.rating, 5)
        self.assertRedirects(self.client.get(reverse("review", args=[a.pk])), reverse("my_applications"))

    def test_cannot_review_foreign_application(self):
        a = self.app(self.past, self.done, user=self.other)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("review", args=[a.pk])).status_code, 404)

    def test_review_text_too_short(self):
        a = self.app(self.past, self.done)
        self.client.force_login(self.user)
        r = self.client.post(reverse("review", args=[a.pk]), {"rating": 4, "text": "ок"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(hasattr(Application.objects.get(pk=a.pk), "review"))

    def test_room_and_payment_from_lists_only(self):
        form = ApplicationForm({"room": "Подвал", "payment": "Биткоины"}, user=self.user, event=self.future)
        self.assertFalse(form.is_valid())
        self.assertIn("room", form.errors)
        self.assertIn("payment", form.errors)

    def test_admin_filter_by_status_and_event(self):
        self.app(self.past, self.done)
        self.app(self.future, self.new, user=self.other)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("manage"), {"status": self.new.pk})
        self.assertEqual([a.status.name for a in r.context["applications"]], ["новая"])
        r = self.client.get(reverse("manage"), {"event": self.past.pk})
        self.assertEqual([a.event.title for a in r.context["applications"]], ["Прошедшее"])
        self.assertEqual(len(self.client.get(reverse("manage")).context["applications"]), 2)


class CrudAndFlowTests(TestCase):
    def setUp(self):
        self.admin = make_user("boss", "Администраторы")
        self.user = make_user("anna")
        self.event = make_event(days=7, title="Для проверок")
        self.new = Status.objects.get(name="новая")

    def event_data(self, **kw):
        data = {"title": "Новая встреча", "description": "Описание встречи", "starts_at": "2027-03-01T10:00",
                "city": "Москва", "place": "Зал 1", "image": "event-1.jpg"}
        data.update(kw)
        return data

    def test_admin_creates_edits_deletes_event(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("event_create"), self.event_data())
        self.assertRedirects(r, reverse("manage_events"))
        ev = Event.objects.get(title="Новая встреча")
        self.client.post(reverse("event_edit", args=[ev.pk]), self.event_data(title="Встреча изменена"))
        ev.refresh_from_db()
        self.assertEqual(ev.title, "Встреча изменена")
        self.client.post(reverse("event_delete", args=[ev.pk]))
        self.assertFalse(Event.objects.filter(pk=ev.pk).exists())

    def test_event_title_too_short(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("event_create"), self.event_data(title="Ab"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Event.objects.filter(title="Ab").exists())

    def test_participant_cannot_manage_events(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("manage_events")).status_code, 403)
        self.assertEqual(self.client.post(reverse("event_create"), self.event_data()).status_code, 403)
        self.assertEqual(self.client.post(reverse("event_delete", args=[self.event.pk])).status_code, 403)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_status_goes_in_order_and_stops(self):
        app = Application.objects.create(user=self.user, event=self.event, status=self.new, room="Малый зал", payment="Банковская карта")
        names = []
        for _ in range(3):
            app.advance()
            names.append(app.status.name)
        self.assertEqual(names, ["назначено", "завершено", "завершено"])

    def test_user_cancels_only_new_application(self):
        app = Application.objects.create(user=self.user, event=self.event, status=self.new, room="Малый зал", payment="Банковская карта")
        self.client.force_login(self.user)
        self.client.post(reverse("cancel_application", args=[app.pk]))
        self.assertFalse(Application.objects.filter(pk=app.pk).exists())
        app = Application.objects.create(user=self.user, event=self.event, status=Status.objects.get(name="назначено"), room="Малый зал", payment="Банковская карта")
        self.client.post(reverse("cancel_application", args=[app.pk]))
        self.assertTrue(Application.objects.filter(pk=app.pk).exists())

    def test_event_rating_is_average_of_reviews(self):
        done = Status.objects.get(name="завершено")
        past = make_event(days=-2, title="Прошедшая")
        self.assertIsNone(past.rating())
        for name, rating in (("u1", 5), ("u2", 4)):
            app = Application.objects.create(user=make_user(name), event=past, status=done, room="Малый зал", payment="Банковская карта")
            Review.objects.create(application=app, rating=rating, text="Хороший день")
        self.assertEqual(past.rating(), 4.5)
        r = self.client.get(reverse("event_detail", args=[past.pk]))
        self.assertContains(r, "★ 4,5")


class FixesAfterTestingTests(TestCase):
    """Проверки на ошибки, найденные при тестировании (МДК.05.03)."""
    data = {"username": "elya_t", "email": "elya@example.com", "phone": "+79161234567",
            "password1": "Proverka-2026", "password2": "Proverka-2026"}

    def test_login_taken_in_other_case(self):
        make_user("admin")
        self.assertIn("username", RegisterForm({**self.data, "username": "ADMIN"}).errors)

    def test_password_of_spaces_rejected(self):
        form = RegisterForm({**self.data, "password1": " " * 8, "password2": " " * 8})
        self.assertIn("password1", form.errors)

    def test_password_equal_to_login_rejected(self):
        form = RegisterForm({**self.data, "username": "elya_test", "password1": "elya_test", "password2": "elya_test"})
        self.assertIn("password1", form.errors)

    def test_email_longer_than_254_rejected(self):
        self.assertIn("email", RegisterForm({**self.data, "email": "a" * 243 + "@example.com"}).errors)

    def test_review_rating_out_of_range_rejected(self):
        from .forms import ReviewForm
        for bad in (0, 6, 100):
            self.assertIn("rating", ReviewForm({"rating": bad, "text": "Достаточно длинный текст"}).errors, bad)
        self.assertTrue(ReviewForm({"rating": 3, "text": "Достаточно длинный текст"}).is_valid())

    def test_logged_in_user_leaves_register_and_login(self):
        self.client.force_login(make_user("anna"))
        self.assertRedirects(self.client.get(reverse("register")), reverse("home"))
        self.assertRedirects(self.client.get(reverse("login")), reverse("home"))

    def test_favicon_is_connected(self):
        r = self.client.get(reverse("home"))
        self.assertContains(r, 'rel="icon"')
        self.assertEqual(self.client.get("/favicon.ico").status_code, 301)
