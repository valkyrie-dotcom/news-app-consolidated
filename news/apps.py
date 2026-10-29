"""App configuration, and the role groups created after migrating."""
from django.apps import AppConfig
from django.db.models.signals import post_migrate

# The permissions each role's group gets (per the brief)
GROUP_PERMISSIONS = {
    "Readers": ["view_article", "view_newsletter"],
    "Editors": [
        "view_article", "change_article", "delete_article",
        "view_newsletter", "change_newsletter", "delete_newsletter",
    ],
    "Journalists": [
        "add_article", "view_article", "change_article", "delete_article",
        "add_newsletter", "view_newsletter", "change_newsletter",
        "delete_newsletter",
    ],
    # Publishers read like readers and choose their publication's staff
    "Publishers": [
        "view_article", "view_newsletter", "view_publisher",
        "change_publisher",
    ],
}


def create_groups(sender, **kwargs):
    """Create the role groups and give them their permissions."""
    from django.contrib.auth.models import Group, Permission

    for group_name, codenames in GROUP_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=group_name)
        group.permissions.set(Permission.objects.filter(
            content_type__app_label="news", codename__in=codenames
        ))


class NewsConfig(AppConfig):
    """Configuration for the news app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "news"

    def ready(self):
        """Create the role groups each time migrations run."""
        # Runs after "migrate", once the permissions exist
        post_migrate.connect(create_groups, sender=self)
