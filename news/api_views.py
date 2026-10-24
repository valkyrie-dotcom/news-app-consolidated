"""Views for RESTful API (token authentication and role-based
access)."""
import logging

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Article, Newsletter, User
from .serializers import ArticleSerializer, NewsletterSerializer
from .utils import approve_article

logger = logging.getLogger(__name__)


def can_manage(user, article):
    """Editors can manage any article, journalists only their own."""
    return user.role == User.EDITOR or article.author == user


def may_use_publisher(user, publisher):
    """Journalists can only write for publishers they belong to."""
    if publisher is None or user.role != User.JOURNALIST:
        return True
    return publisher.journalists.filter(pk=user.pk).exists()


def error(message, code):
    """Return an error response in one consistent format."""
    return Response({"error": message}, status=code)


@api_view(["GET", "POST"])
def article_list(request):
    """GET: all approved articles. POST: create an article (journalists)."""
    if request.method == "GET":
        articles = Article.objects.filter(approved=True)
        return Response(ArticleSerializer(articles, many=True).data)

    user = request.user
    if user.role != User.JOURNALIST or not user.has_perm("news.add_article"):
        return error("Only journalists can create articles.",
                     status.HTTP_403_FORBIDDEN)

    serializer = ArticleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if not may_use_publisher(user, serializer.validated_data.get("publisher")):
        return error("You are not a journalist for this publisher.",
                     status.HTTP_403_FORBIDDEN)

    # New articles always wait for an editor's approval
    serializer.save(author=user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def subscribed_articles(request):
    """Approved articles from the reader's subscribed publishers and
    journalists."""
    user = request.user
    if user.role != User.READER:
        return error("Only readers have subscriptions.",
                     status.HTTP_403_FORBIDDEN)

    articles = Article.objects.filter(approved=True).filter(
        Q(publisher__in=user.subscribed_publishers.all())
        | Q(author__in=user.subscribed_journalists.all())
    ).distinct()
    return Response(ArticleSerializer(articles, many=True).data)


@api_view(["GET", "PUT", "DELETE"])
def article_detail(request, pk):
    """GET one article. PUT updates it, DELETE removes it (editors, or the
    journalist who wrote it). Only editors can approve with PUT."""
    article = get_object_or_404(Article, pk=pk)
    user = request.user

    if request.method == "GET":
        # Unapproved articles are hidden from everyone but editors and
        # their author
        if not article.approved and not can_manage(user, article):
            return error("Article not found.", status.HTTP_404_NOT_FOUND)
        return Response(ArticleSerializer(article).data)

    if request.method == "DELETE":
        if not user.has_perm("news.delete_article") or \
                not can_manage(user, article):
            return error("You cannot delete this article.",
                         status.HTTP_403_FORBIDDEN)
        article.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT
    if not user.has_perm("news.change_article") or \
            not can_manage(user, article):
        return error("You cannot update this article.",
                     status.HTTP_403_FORBIDDEN)

    approve = None
    if "approved" in request.data:
        if user.role != User.EDITOR:
            return error("Only editors can approve articles.",
                         status.HTTP_403_FORBIDDEN)
        try:
            approve = serializers.BooleanField().to_internal_value(
                request.data["approved"]
            )
        except serializers.ValidationError:
            return error("approved must be true or false.",
                         status.HTTP_400_BAD_REQUEST)

    serializer = ArticleSerializer(article, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if not may_use_publisher(user, serializer.validated_data.get("publisher")):
        return error("You are not a journalist for this publisher.",
                     status.HTTP_403_FORBIDDEN)
    article = serializer.save()

    if approve is True and not article.approved:
        # Approves, emails subscribers and posts to /api/approved/
        approve_article(article, user)
    elif approve is False and article.approved:
        article.approved = False
        article.save()
    return Response(ArticleSerializer(article).data)


@api_view(["POST"])
def approved_log(request):
    """Log an approved article. Called after an editor approves one."""
    if request.user.role != User.EDITOR:
        return error("Only editors can log approved articles.",
                     status.HTTP_403_FORBIDDEN)
    title = request.data.get("title")
    if not title:
        return error("The article title is required.",
                     status.HTTP_400_BAD_REQUEST)
    logger.info("Approved article logged: %s (id %s)",
                title, request.data.get("id"))
    return Response({"logged": title}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def newsletter_list(request):
    """All newsletters."""
    newsletters = Newsletter.objects.all()
    return Response(NewsletterSerializer(newsletters, many=True).data)


@api_view(["GET"])
def newsletter_detail(request, pk):
    """One newsletter."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return Response(NewsletterSerializer(newsletter).data)
