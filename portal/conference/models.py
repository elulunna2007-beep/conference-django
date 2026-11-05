from django.contrib.auth.models import User
from django.db import models
from django.db.models import Avg
from django.utils import timezone


class Profile(models.Model):
    """Дополнительные данные пользователя: телефон. Роль задаётся группой пользователя."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField("Телефон", max_length=20)

    class Meta:
        verbose_name = "профиль"
        verbose_name_plural = "профили"

    def __str__(self):
        return self.user.username


class Status(models.Model):
    """Справочник статусов заявки: новая, назначено, завершено."""
    name = models.CharField("Название", max_length=20, unique=True)
    position = models.PositiveSmallIntegerField("Порядок", unique=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "статус"
        verbose_name_plural = "статусы"

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField("Название", max_length=150)
    description = models.TextField("Описание")
    starts_at = models.DateTimeField("Дата и время")
    city = models.CharField("Город", max_length=60)
    place = models.CharField("Место", max_length=120)
    image = models.CharField("Файл фото", max_length=80, blank=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "мероприятие"
        verbose_name_plural = "мероприятия"

    def __str__(self):
        return self.title

    def is_finished(self):
        return self.starts_at < timezone.now()

    def rating(self):
        """Средняя оценка по отзывам или None, если отзывов нет."""
        avg = Review.objects.filter(application__event=self).aggregate(a=Avg("rating"))["a"]
        return round(avg, 1) if avg else None


ROOMS = ["Большой зал", "Малый зал", "Онлайн-трансляция"]
PAYMENTS = ["Банковская карта", "Наличные при регистрации", "Счёт для организации"]


class Application(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applications")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="applications")
    status = models.ForeignKey(Status, on_delete=models.PROTECT)
    room = models.CharField("Помещение", max_length=60, choices=[(r, r) for r in ROOMS])
    payment = models.CharField("Способ оплаты", max_length=40, choices=[(p, p) for p in PAYMENTS])
    comment = models.CharField("Комментарий", max_length=200, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        constraints = [
            # одна заявка участника на одно мероприятие; проверка в форме есть, это защита на уровне базы
            models.UniqueConstraint(fields=["user", "event"], name="one_application_per_event"),
        ]

    def __str__(self):
        return "%s: %s" % (self.user.username, self.event.title)

    def advance(self):
        """Переводит заявку на следующий статус: новая, назначено, завершено. Пропускать статусы нельзя."""
        following = Status.objects.filter(position__gt=self.status.position).first()
        if following:
            self.status = following
            self.save()
        return following

    def can_review(self):
        """Отзыв можно оставить, когда заявка завершена, мероприятие прошло и отзыва ещё нет."""
        return self.status.name == "завершено" and self.event.is_finished() and not hasattr(self, "review")


class Review(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField("Оценка")
    text = models.TextField("Текст отзыва")
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"

    def __str__(self):
        return "Отзыв на %s" % self.application
