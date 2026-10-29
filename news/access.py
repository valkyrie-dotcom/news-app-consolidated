"""Who can see and manage articles and newsletters.

Editors only see articles and newsletters of publishers they are
assigned to. Everyone else sees all approved content, journalists also
see their own unapproved articles.
"""
from .models import Article, Newsletter, User


def is_editor(user):
    """Return True if the user has the Editor role."""
    return user.role == User.EDITOR


def listed_articles(user):
    """Approved articles for the user's article list (editors only get
    their publishers' articles)."""
    articles = Article.objects.filter(approved=True)
    if is_editor(user):
        articles = articles.filter(publisher__editors=user)
    return articles


def articles_to_review(user):
    """Unapproved articles of the editor's publishers."""
    return Article.objects.filter(approved=False, publisher__editors=user)


def can_view_article(user, article):
    """Editors may open their publishers' articles. Everyone else may open
    approved articles, and journalists their own."""
    if is_editor(user):
        return (article.publisher is not None
                and article.publisher.editors.filter(pk=user.pk).exists())
    return article.approved or article.author == user


def can_manage_article(user, article):
    """Editors may manage their publishers' articles, journalists their
    own."""
    if is_editor(user):
        return can_view_article(user, article)
    return article.author == user


def listed_newsletters(user):
    """Newsletters the user may see. Editors only get newsletters written
    by journalists of their publishers."""
    if is_editor(user):
        return Newsletter.objects.filter(
            author__journalist_of__editors=user
        ).distinct()
    return Newsletter.objects.all()


def can_view_newsletter(user, newsletter):
    """Return True if the newsletter is one the user may see."""
    return listed_newsletters(user).filter(pk=newsletter.pk).exists()


def can_manage_newsletter(user, newsletter):
    """Editors may manage the newsletters they can see, journalists their
    own."""
    if is_editor(user):
        return can_view_newsletter(user, newsletter)
    return newsletter.author == user


def editor_without_publisher(user):
    """Return True for an editor who has not been added to a publisher."""
    return is_editor(user) and not user.editor_of.exists()
