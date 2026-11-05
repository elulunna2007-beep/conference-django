def roles(request):
    """Роль текущего пользователя для шаблонов: is_admin и is_participant."""
    u = request.user
    admin = u.is_authenticated and u.groups.filter(name="Администраторы").exists()
    return {"is_admin": admin, "is_participant": u.is_authenticated and not admin}
