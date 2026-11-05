from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from conference.models import Application, Event, Profile, Review, Status

EVENTS = [
    # название, город, место, дней от сегодня, фото, описание
    ("Основы тестирования: открытый митап", "Москва", "Дом инженеров, зал 2", -38, "event-1.jpg",
     "Вечер для начинающих тестировщиков. Разбираем чек-листы, тест-кейсы и первый баг-репорт на живом примере."),
    ("Фронтенд-день", "Москва", "Технопарк «Северный»", -16, "event-2.jpg",
     "Шесть коротких докладов про вёрстку, доступность и скорость загрузки страниц. Между докладами кофе и вопросы."),
    ("Школа наставников", "Тула", "Областной центр образования", -5, "event-3.jpg",
     "Как помогать новичкам на работе: разбор ошибок, обратная связь, план роста на три месяца."),
    ("Python в работе: данные и автоматизация", "Москва", "Дом инженеров, большой зал", 12, "event-4.jpg",
     "Скрипты для отчётов, разбор таблиц и работа с API. Практикум на ноутбуках, ноутбук можно взять свой."),
    ("Учитель цифровой эпохи", "Казань", "Университет, аудитория 301", 25, "event-5.jpg",
     "Электронные журналы, онлайн-тесты и защита данных школьников. Выступают учителя и методисты."),
    ("Умный город: транспорт и общественные пространства", "Москва", "Центр урбанистики", 40, "event-6.jpg",
     "Круглый стол о маршрутах, остановках и дворах. Разбираем реальные проекты и считаем их стоимость."),
    ("Телемедицина на практике", "Москва", "Медицинский колледж, актовый зал", 58, "event-7.jpg",
     "Как проходит онлайн-приём, что нужно врачу и пациенту, как хранить записи. Есть онлайн-трансляция."),
    ("Бренд без бюджета", "Нижний Новгород", "Бизнес-инкубатор, зал «Волга»", 85, "event-8.jpg",
     "Маркетинг для малого бизнеса: название, упаковка, соцсети и первые продажи без рекламного бюджета."),
    ("Безопасность веб-приложений для начинающих", "Москва", "Технопарк «Северный», зал 4", 120, "event-9.jpg",
     "Пароли, сессии, формы и права доступа. Показываем атаки на учебном сайте и способы защиты."),
]

USERS = [
    ("anna_k", "anna.k@example.com", "+79161234501"),
    ("dmitry_s", "dmitry.s@example.com", "+79161234502"),
    ("maria_v", "maria.v@example.com", "+79161234503"),
]
ADMIN_PASSWORD = "Admin-2026-Konf"
USER_PASSWORD = "Konf-2026-user"


class Command(BaseCommand):
    help = "Заполняет базу учебными данными: мероприятия, пользователи, заявки, отзывы"

    def handle(self, *args, **options):
        if Event.objects.exists():
            self.stdout.write("Данные уже есть, пропускаю")
            return
        now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        events = []
        for title, city, place, days, image, text in EVENTS:
            events.append(Event.objects.create(title=title, city=city, place=place, image=image,
                                               description=text, starts_at=now + timedelta(days=days)))
        admin = User.objects.create_user("admin", "admin@example.com", ADMIN_PASSWORD, is_staff=True, is_superuser=True)
        admin.groups.add(Group.objects.get(name="Администраторы"))
        Profile.objects.create(user=admin, phone="+79160000000")
        users = []
        for login, mail, phone in USERS:
            u = User.objects.create_user(login, mail, USER_PASSWORD)
            u.groups.add(Group.objects.get(name="Участники"))
            Profile.objects.create(user=u, phone=phone)
            users.append(u)
        new, assigned, done = [Status.objects.get(name=n) for n in ("новая", "назначено", "завершено")]
        rows = [
            (users[0], events[0], done, "Большой зал", "Банковская карта"),
            (users[1], events[0], done, "Малый зал", "Наличные при регистрации"),
            (users[0], events[1], done, "Большой зал", "Банковская карта"),
            (users[2], events[1], assigned, "Малый зал", "Счёт для организации"),
            (users[0], events[3], new, "Большой зал", "Банковская карта"),
            (users[1], events[3], assigned, "Большой зал", "Наличные при регистрации"),
            (users[2], events[5], new, "Малый зал", "Банковская карта"),
        ]
        apps = [Application.objects.create(user=u, event=e, status=s, room=r, payment=p) for u, e, s, r, p in rows]
        Review.objects.create(application=apps[0], rating=5, text="Разобрали настоящий баг-репорт, после митапа сама написала первый.")
        Review.objects.create(application=apps[1], rating=4, text="Полезно, но хотелось больше практики и меньше слайдов.")
        self.stdout.write("Готово: %d мероприятий, %d пользователей, %d заявок" % (len(events), len(users) + 1, len(apps)))
