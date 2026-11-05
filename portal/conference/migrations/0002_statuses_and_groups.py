from django.db import migrations


def fill(apps, schema_editor):
    Status = apps.get_model("conference", "Status")
    Group = apps.get_model("auth", "Group")
    for position, name in enumerate(["новая", "назначено", "завершено"], 1):
        Status.objects.get_or_create(name=name, defaults={"position": position})
    for name in ["Участники", "Администраторы"]:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("conference", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
