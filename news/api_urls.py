"""URL patterns for RESTful API."""
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import api_views

urlpatterns = [
    # POST a username and password to get a token
    path("token/", obtain_auth_token, name="api_token"),

    # Articles
    path("articles/", api_views.article_list, name="api_articles"),
    path(
        "articles/subscribed/",
        api_views.subscribed_articles, name="api_subscribed_articles",
    ),
    path(
        "articles/<int:pk>/",
        api_views.article_detail, name="api_article_detail",
    ),

    # Approved articles are posted here after approval
    path("approved/", api_views.approved_log, name="api_approved"),

    # Newsletters (read-only)
    path("newsletters/", api_views.newsletter_list, name="api_newsletters"),
    path(
        "newsletters/<int:pk>/",
        api_views.newsletter_detail, name="api_newsletter_detail",
    ),
]
