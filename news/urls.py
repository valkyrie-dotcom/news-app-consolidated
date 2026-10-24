"""URL patterns for the website pages."""
from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    # Accounts
    path("login/", views.login_user, name="login"),
    path("register/", views.register_user, name="register"),
    path("logout/", views.logout_user, name="logout"),

    # Articles
    path("", views.article_list, name="article_list"),
    path("articles/<int:pk>/", views.article_detail, name="article_detail"),
    path("articles/new/", views.article_create, name="article_create"),
    path("articles/<int:pk>/edit/", views.article_edit, name="article_edit"),
    path(
        "articles/<int:pk>/delete/",
        views.article_delete, name="article_delete",
    ),
    path("my-articles/", views.my_articles, name="my_articles"),

    # Editors
    path("review/", views.review_articles, name="review_articles"),
    path(
        "review/<int:pk>/approve/",
        views.approve_article_view, name="approve_article",
    ),

    # Newsletters
    path("newsletters/", views.newsletter_list, name="newsletter_list"),
    path(
        "newsletters/<int:pk>/",
        views.newsletter_detail, name="newsletter_detail",
    ),
    path(
        "newsletters/new/",
        views.newsletter_create, name="newsletter_create",
    ),
    path(
        "newsletters/<int:pk>/edit/",
        views.newsletter_edit, name="newsletter_edit",
    ),
    path(
        "newsletters/<int:pk>/delete/",
        views.newsletter_delete, name="newsletter_delete",
    ),

    # Readers
    path("subscriptions/", views.subscriptions, name="subscriptions"),
]
