"""Admin pages for users, publishers, articles and newsletters."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Article, Newsletter, Publisher, User


@admin.register(User)
class NewsUserAdmin(UserAdmin):
    """Show the role and subscriptions on the user admin page."""

    list_display = ["username", "email", "role", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        ("News", {"fields": (
            "role", "subscribed_publishers", "subscribed_journalists",
        )}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("News", {"fields": ("email", "role")}),
    )

    def save_related(self, request, form, formsets, change):
        """Save the user's groups and subscriptions, then apply the role
        rules again."""
        # The admin saves groups and subscriptions after the user, so
        # apply the role rules again afterwards
        super().save_related(request, form, formsets, change)
        form.instance.apply_role()


admin.site.register(Publisher)
admin.site.register(Article)
admin.site.register(Newsletter)
