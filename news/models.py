"""Models for users with roles, publishers, articles and newsletters."""
from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class User(AbstractUser):
    """A user of the news application with a role.

    Readers subscribe to publishers and journalists. Journalists write
    articles and newsletters. Editors review and approve their publishers'
    articles. Publishers own a publication and choose its editors and
    journalists.
    """

    READER = "reader"
    EDITOR = "editor"
    JOURNALIST = "journalist"
    PUBLISHER = "publisher"
    ROLE_CHOICES = [
        (READER, "Reader"),
        (EDITOR, "Editor"),
        (JOURNALIST, "Journalist"),
        (PUBLISHER, "Publisher"),
    ]

    # The group each role is added to
    ROLE_GROUPS = {
        READER: "Readers",
        EDITOR: "Editors",
        JOURNALIST: "Journalists",
        PUBLISHER: "Publishers",
    }

    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default=READER
    )

    # Reader fields: the publishers and journalists they subscribe to
    subscribed_publishers = models.ManyToManyField(
        "Publisher", blank=True, related_name="subscribers"
    )
    subscribed_journalists = models.ManyToManyField(
        "self", blank=True, symmetrical=False,
        related_name="reader_subscribers",
    )

    def save(self, *args, **kwargs):
        """Save the user, then apply their role's group and fields.

        :param args: Positional arguments passed on to Django's ``save()``
        :param kwargs: Keyword arguments passed on to Django's ``save()``
        """
        super().save(*args, **kwargs)
        self.apply_role()

    def apply_role(self):
        """Put the user in their role's group.

        Users who are not readers have their subscriptions cleared, because
        only readers have subscriptions.
        """
        group = Group.objects.filter(name=self.ROLE_GROUPS[self.role]).first()
        if group is not None:
            self.groups.set([group])
        # Only readers have subscriptions, so other roles have none
        if self.role != self.READER:
            self.subscribed_publishers.clear()
            self.subscribed_journalists.clear()

    # Journalist fields. The articles and newsletters are reverse
    # relations of Article.author and Newsletter.author.
    @property
    def independent_articles(self):
        """Articles a journalist published without a publisher.

        :returns: The journalist's independent articles, or ``None`` for
            users who are not journalists
        :rtype: QuerySet or None
        """
        if self.role != self.JOURNALIST:
            return None
        return self.articles.filter(publisher__isnull=True)

    @property
    def independent_newsletters(self):
        """Newsletters a journalist created.

        :returns: The journalist's newsletters, or ``None`` for users who
            are not journalists
        :rtype: QuerySet or None
        """
        if self.role != self.JOURNALIST:
            return None
        return self.newsletters.all()

    def __str__(self):
        """Return the username."""
        return self.username


class Publisher(models.Model):
    """A publication that can have several editors and journalists.

    A user with the Publisher role owns the publication and chooses its
    editors and journalists.
    """

    name = models.CharField(max_length=100, unique=True)
    # The publisher user who owns this publication.
    owner = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="publication",
        limit_choices_to={"role": User.PUBLISHER},
    )
    editors = models.ManyToManyField(
        User, blank=True, related_name="editor_of",
        limit_choices_to={"role": User.EDITOR},
    )
    journalists = models.ManyToManyField(
        User, blank=True, related_name="journalist_of",
        limit_choices_to={"role": User.JOURNALIST},
    )

    def __str__(self):
        """Return the publisher's name."""
        return self.name


class Article(models.Model):
    """A news article written by a journalist."""

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="articles"
    )
    publisher = models.ForeignKey(
        Publisher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="articles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # True once an editor has approved the article
    approved = models.BooleanField(default=False)

    class Meta:
        """Show the newest articles first."""

        ordering = ["-created_at"]

    def __str__(self):
        """Return the article's title."""
        return self.title


class Newsletter(models.Model):
    """A collection of articles created by a journalist."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="newsletters"
    )
    articles = models.ManyToManyField(
        Article, blank=True, related_name="newsletters"
    )

    class Meta:
        """Show newest newsletters first."""

        ordering = ["-created_at"]

    def __str__(self):
        """Return newsletter's title."""
        return self.title
