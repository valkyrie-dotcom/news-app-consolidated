"""URL configuration for the news_site project."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("news.api_urls")),
    path("", include("news.urls")),
]
