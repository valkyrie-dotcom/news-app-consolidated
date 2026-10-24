"""DRF serializers for users, publishers, articles and newsletters.
Largely adapted from previous lessons and tasks."""
from rest_framework import serializers

from .models import Article, Newsletter, Publisher, User


class UserSerializer(serializers.ModelSerializer):
    """Convert a user to JSON (ID, username and role)."""

    class Meta:
        """Use the User model and these fields."""

        model = User
        fields = ["id", "username", "role"]


class PublisherSerializer(serializers.ModelSerializer):
    """Convert a publisher to JSON (ID and name)."""

    class Meta:
        """Use the Publisher model and these fields."""

        model = Publisher
        fields = ["id", "name"]


class ArticleSerializer(serializers.ModelSerializer):
    """Convert an article to and from JSON."""

    # The author is the logged-in journalist, so it is never sent in
    author = UserSerializer(read_only=True)
    # The publisher is sent as an ID and shown with its name
    publisher = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.all(), allow_null=True, required=False
    )
    publisher_detail = PublisherSerializer(source="publisher", read_only=True)

    class Meta:
        """Use the Article model and these fields."""

        model = Article
        fields = [
            "id", "title", "content", "author", "publisher",
            "publisher_detail", "created_at", "approved",
        ]
        # Approval is handled separately
        read_only_fields = ["created_at", "approved"]


class NewsletterSerializer(serializers.ModelSerializer):
    """Convert a newsletter and its approved articles to JSON."""

    author = UserSerializer(read_only=True)
    articles = serializers.SerializerMethodField()

    def get_articles(self, newsletter):
        """Only approved articles are shown in a newsletter."""
        approved = newsletter.articles.filter(approved=True)
        return ArticleSerializer(approved, many=True).data

    class Meta:
        """Use the Newsletter model and these fields."""

        model = Newsletter
        fields = [
            "id", "title", "description", "created_at", "author", "articles",
        ]
