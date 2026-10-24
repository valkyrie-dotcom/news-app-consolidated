"""Views for the website pages (accounts, articles, review and approval,
newsletters and subscriptions)"""
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ArticleForm, NewsletterForm, SubscriptionForm
from .models import Article, Newsletter, User
from .utils import approve_article


def forbidden(request, message):
    """Show an error page when a user may not do something."""
    return render(
        request, "news/forbidden.html", {"error": message}, status=403
    )


def can_manage(user, item):
    """Editors can manage any article or newsletter, journalists only
    their own."""
    return user.role == User.EDITOR or item.author == user


# ---------- Accounts ----------

def login_user(request):
    """Log a user in with their username and password."""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            request.session.set_expiry(3600)  # Session lasts one hour
            return redirect("news:article_list")
        return render(
            request, "news/login.html", {"error": "Invalid credentials"}
        )
    return render(request, "news/login.html")


def register_user(request):
    """Register a new Reader, Journalist or Editor."""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        password_conf = request.POST.get("password_conf")
        role = request.POST.get("role")

        # Check the input before creating the user
        error = None
        if not username:
            error = "Please enter a username."
        elif User.objects.filter(username=username).exists():
            error = "That username is already taken."
        elif not email:
            error = "Please enter an email address."
        # Each email address can only be used once, so article emails go
        # to the right person
        elif User.objects.filter(email__iexact=email).exists():
            error = "An account with that email address already exists."
        elif role not in (User.READER, User.JOURNALIST, User.EDITOR):
            error = "Please choose Reader, Journalist or Editor."
        elif not password:
            error = "Please enter a password."
        elif password != password_conf:
            error = "Passwords do not match."
        else:
            try:
                validate_password(password, User(username=username))
            except ValidationError as problems:
                error = " ".join(problems.messages)

        if error:
            return render(request, "news/register.html", {"error": error})

        # Saving the user also puts them in their role's group
        user = User.objects.create_user(
            username=username, email=email, password=password, role=role
        )
        login(request, user)
        return redirect("news:article_list")
    return render(request, "news/register.html")


def logout_user(request):
    """Log the user out."""
    logout(request)
    return redirect("news:login")


# ---------- Articles ----------

@login_required
def article_list(request):
    """Show all approved articles."""
    if not request.user.has_perm("news.view_article"):
        return forbidden(request, "You do not have permission to view "
                                  "articles.")
    articles = Article.objects.filter(approved=True)
    return render(request, "news/article_list.html", {"articles": articles})


@login_required
def article_detail(request, pk):
    """Show one article."""
    user = request.user
    if not user.has_perm("news.view_article"):
        return forbidden(request, "You do not have permission to view "
                                  "articles.")
    article = get_object_or_404(Article, pk=pk)
    # Unapproved articles are only shown to editors and their author
    if not article.approved and not can_manage(user, article):
        raise Http404("Article not found.")
    return render(request, "news/article_detail.html", {"article": article})


@login_required
def my_articles(request):
    """Show a journalist's own articles and their status."""
    if request.user.role != User.JOURNALIST:
        return forbidden(request, "Only journalists have articles.")
    articles = request.user.articles.all()
    return render(request, "news/my_articles.html", {"articles": articles})


@login_required
def article_create(request):
    """Let a journalist write a new article."""
    user = request.user
    if not user.has_perm("news.add_article"):
        return forbidden(request, "Only journalists can write articles.")
    form = ArticleForm(request.POST or None, journalist=user)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = user
        article.save()
        messages.success(request, "Article submitted for review.")
        return redirect("news:my_articles")
    return render(request, "news/article_form.html", {
        "form": form, "heading": "Write an article",
    })


@login_required
def article_edit(request, pk):
    """Let an editor or the article's journalist edit it."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)
    if not user.has_perm("news.change_article") or \
            not can_manage(user, article):
        return forbidden(request, "You cannot edit this article.")
    form = ArticleForm(
        request.POST or None, instance=article, journalist=article.author
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Article updated.")
        return redirect("news:article_detail", pk=article.pk)
    return render(request, "news/article_form.html", {
        "form": form, "heading": "Edit article",
    })


@login_required
def article_delete(request, pk):
    """Let an editor or the article's journalist delete it."""
    user = request.user
    article = get_object_or_404(Article, pk=pk)
    if not user.has_perm("news.delete_article") or \
            not can_manage(user, article):
        return forbidden(request, "You cannot delete this article.")
    if request.method == "POST":
        article.delete()
        messages.success(request, "Article deleted.")
        return redirect("news:article_list")
    return render(request, "news/confirm_delete.html", {"item": article})


# ---------- Editors: review and approve ----------

@login_required
def review_articles(request):
    """Show editors the articles waiting for approval."""
    if request.user.role != User.EDITOR:
        return forbidden(request, "Only editors can review articles.")
    articles = Article.objects.filter(approved=False)
    return render(request, "news/review_articles.html", {
        "articles": articles,
    })


@login_required
def approve_article_view(request, pk):
    """Approve an article (editors only)."""
    if request.user.role != User.EDITOR:
        return forbidden(request, "Only editors can approve articles.")
    article = get_object_or_404(Article, pk=pk, approved=False)
    if request.method == "POST":
        # Approves, emails subscribers and posts to /api/approved/
        sent = approve_article(article, request.user)
        messages.success(
            request, f"'{article.title}' approved and emailed to "
                     f"{sent} subscriber(s)."
        )
    return redirect("news:review_articles")


# ---------- Newsletters ----------

@login_required
def newsletter_list(request):
    """Show all newsletters."""
    if not request.user.has_perm("news.view_newsletter"):
        return forbidden(request, "You do not have permission to view "
                                  "newsletters.")
    newsletters = Newsletter.objects.all()
    return render(request, "news/newsletter_list.html", {
        "newsletters": newsletters,
    })


@login_required
def newsletter_detail(request, pk):
    """Show one newsletter and its approved articles."""
    if not request.user.has_perm("news.view_newsletter"):
        return forbidden(request, "You do not have permission to view "
                                  "newsletters.")
    newsletter = get_object_or_404(Newsletter, pk=pk)
    # Readers only see the approved articles in a newsletter
    articles = newsletter.articles.filter(approved=True)
    return render(request, "news/newsletter_detail.html", {
        "newsletter": newsletter, "articles": articles,
    })


@login_required
def newsletter_create(request):
    """Let a journalist create a newsletter."""
    user = request.user
    if not user.has_perm("news.add_newsletter"):
        return forbidden(request, "Only journalists can create "
                                  "newsletters.")
    form = NewsletterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        newsletter = form.save(commit=False)
        newsletter.author = user
        newsletter.save()
        form.save_m2m()  # Saves chosen articles
        messages.success(request, "Newsletter created.")
        return redirect("news:newsletter_detail", pk=newsletter.pk)
    return render(request, "news/newsletter_form.html", {
        "form": form, "heading": "Create a newsletter",
    })


@login_required
def newsletter_edit(request, pk):
    """Let an editor or the newsletter's journalist edit it."""
    user = request.user
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not user.has_perm("news.change_newsletter") or \
            not can_manage(user, newsletter):
        return forbidden(request, "You cannot edit this newsletter.")
    form = NewsletterForm(request.POST or None, instance=newsletter)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Newsletter updated.")
        return redirect("news:newsletter_detail", pk=newsletter.pk)
    return render(request, "news/newsletter_form.html", {
        "form": form, "heading": "Edit newsletter",
    })


@login_required
def newsletter_delete(request, pk):
    """Let an editor or the newsletter's journalist delete it."""
    user = request.user
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not user.has_perm("news.delete_newsletter") or \
            not can_manage(user, newsletter):
        return forbidden(request, "You cannot delete this newsletter.")
    if request.method == "POST":
        newsletter.delete()
        messages.success(request, "Newsletter deleted.")
        return redirect("news:newsletter_list")
    return render(request, "news/confirm_delete.html", {"item": newsletter})


# ---------- Readers: subscriptions ----------

@login_required
def subscriptions(request):
    """Let a reader choose their subscriptions."""
    user = request.user
    if user.role != User.READER:
        return forbidden(request, "Only readers can subscribe.")
    form = SubscriptionForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Subscriptions saved.")
        return redirect("news:subscriptions")
    return render(request, "news/subscriptions.html", {"form": form})
