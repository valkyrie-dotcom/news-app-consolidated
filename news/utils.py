"""Approval logic (email subscribers and post to /api/approved/)."""
import logging
import smtplib

import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from rest_framework.authtoken.models import Token

from .models import User

logger = logging.getLogger(__name__)


def get_subscriber_emails(article):
    """Find the readers who should receive an approved article.

    :param Article article: The approved article
    :returns: The email addresses of readers subscribed to the article's
        journalist or publisher
    :rtype: list[str]
    """
    subscribed = Q(subscribed_journalists=article.author)
    if article.publisher is not None:
        subscribed |= Q(subscribed_publishers=article.publisher)

    readers = (
        User.objects.filter(role=User.READER)
        .filter(subscribed)
        .exclude(email="")
        .distinct()
    )
    return [reader.email for reader in readers]


def build_article_email(article, recipients):
    """Create the email that sends an approved article to subscribers.

    :param Article article: The approved article
    :param list[str] recipients: The subscribers' email addresses, added as
        BCC so they cannot see each other
    :returns: The email, ready to send
    :rtype: django.core.mail.EmailMessage
    """
    subject = f"New article: {article.title}"
    source = f"By {article.author.username}"
    if article.publisher is not None:
        source += f" for {article.publisher.name}"
    body = f"{article.title}\n{source}\n\n{article.content}"
    # Subscribers are added as BCC so they cannot see each other
    return EmailMessage(subject, body, bcc=recipients)


def email_subscribers(article):
    """Email the article to its subscribers.

    If the email cannot be sent, the error is logged and the approval is
    kept.

    :param Article article: The approved article
    :returns: The number of subscribers emailed (0 if there are none or the
        email failed)
    :rtype: int
    """
    recipients = get_subscriber_emails(article)
    if not recipients:
        return 0
    try:
        build_article_email(article, recipients).send()
    except (smtplib.SMTPException, OSError):
        logger.exception("Could not email article %s", article.pk)
        return 0
    return len(recipients)


def post_to_approved_api(article, user):
    """Send the approved article to our own /api/approved/ endpoint.

    The request uses the API token of the user who published the article:
    the editor, or the journalist for an independent article. If the
    endpoint cannot be reached, the error is logged and the approval is
    kept.

    :param Article article: The approved article
    :param User user: The user who approved or published it
    :returns: The response status code, or ``None`` if the request failed
    :rtype: int or None
    """
    # Imported here to avoid a circular import with serializers.py
    from .serializers import ArticleSerializer

    token, created = Token.objects.get_or_create(user=user)
    try:
        response = requests.post(
            settings.APPROVED_API_URL,
            json=ArticleSerializer(article).data,
            headers={"Authorization": f"Token {token.key}"},
            timeout=5,
        )
    except requests.RequestException:
        logger.exception("Could not post article %s to the API", article.pk)
        return None
    return response.status_code


def approve_article(article, user):
    """Approve an article, email its subscribers and log it to the API.

    Editors approve their publishers' articles on the approve page or with
    the API's PUT. Independent articles are approved when the journalist
    saves them (see :func:`update_article_status`).

    :param Article article: The article to approve
    :param User user: The editor approving it, or the journalist
        publishing an independent article
    :returns: The number of subscribers emailed
    :rtype: int
    """
    article.approved = True
    article.save()
    sent = email_subscribers(article)
    post_to_approved_api(article, user)
    return sent


def update_article_status(article, user, old_publisher_id=None):
    """Publish an independent article as soon as its journalist saves it.

    An article with no publisher is the journalist's own, so it goes live
    when it is saved. An article that is moved under a publisher waits for
    that publisher's editors again.

    :param Article article: The article that was just saved
    :param User user: The journalist who saved it
    :param old_publisher_id: The article's publisher before the save, or
        ``None`` for a new or independent article
    :type old_publisher_id: int or None
    :returns: The number of subscribers emailed (0 if nothing was
        published)
    :rtype: int
    """
    if article.publisher_id is None:
        if not article.approved:
            return approve_article(article, user)
    elif article.publisher_id != old_publisher_id and article.approved:
        # Moved under a (different) publisher, so its editors must approve
        article.approved = False
        article.save()
    return 0
