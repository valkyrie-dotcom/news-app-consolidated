"""Automated unit tests for the news app's RESTful API."""
from unittest import mock

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Article, Newsletter, Publisher, User

PASSWORD = "Str0ng-Pass-123"


# A fast password hasher keeps the tests quick
@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class NewsTestCase(TestCase):
    """Users, a publisher and articles shared by the tests."""

    def setUp(self):
        """Create the users, publisher and articles."""
        self.reader = User.objects.create_user(
            "reader", "reader@example.com", PASSWORD, role=User.READER
        )
        self.editor = User.objects.create_user(
            "editor", "editor@example.com", PASSWORD, role=User.EDITOR
        )
        self.journalist = User.objects.create_user(
            "journalist", "j1@example.com", PASSWORD, role=User.JOURNALIST
        )
        self.other_journalist = User.objects.create_user(
            "other_journalist", "j2@example.com", PASSWORD,
            role=User.JOURNALIST,
        )

        self.publisher = Publisher.objects.create(name="Daily Planet")
        self.publisher.journalists.add(self.journalist)
        # Editors only see and approve their own publishers' articles
        self.publisher.editors.add(self.editor)

        # Approved articles: one from the publisher, one from another
        # journalist, and one article still waiting for approval
        self.publisher_article = Article.objects.create(
            title="Publisher news", content="From the Daily Planet.",
            author=self.journalist, publisher=self.publisher, approved=True,
        )
        self.other_article = Article.objects.create(
            title="Other news", content="From someone else.",
            author=self.other_journalist, approved=True,
        )
        self.pending_article = Article.objects.create(
            title="Pending news", content="Not approved yet.",
            author=self.journalist, publisher=self.publisher,
        )

        self.client = APIClient()

    def login_as(self, user):
        """Send the user's token with every API request."""
        token, created = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")


class AuthenticationTests(NewsTestCase):
    """Token login and authenticated access per role."""

    def test_valid_login_returns_token(self):
        """A valid username and password returns a token."""
        response = self.client.post(reverse("api_token"), {
            "username": "reader", "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())

    def test_request_without_token_is_refused(self):
        """A request without a token gets 401."""
        response = self.client.get(reverse("api_articles"))
        self.assertEqual(response.status_code, 401)

    def test_reader_sees_only_approved_articles(self):
        """Readers only see approved articles."""
        self.login_as(self.reader)
        response = self.client.get(reverse("api_articles"))
        self.assertEqual(response.status_code, 200)
        titles = [article["title"] for article in response.json()]
        self.assertNotIn("Pending news", titles)


class SubscribedArticleTests(NewsTestCase):
    """Readers only get articles from their subscriptions."""

    def test_reader_gets_only_subscribed_content(self):
        """A reader only gets articles they subscribe to."""
        self.reader.subscribed_publishers.add(self.publisher)
        self.login_as(self.reader)
        response = self.client.get(reverse("api_subscribed_articles"))
        self.assertEqual(response.status_code, 200)
        titles = [article["title"] for article in response.json()]
        # Not the pending article, and not the unsubscribed journalist
        self.assertEqual(titles, ["Publisher news"])

    def test_non_reader_is_refused(self):
        """Only readers can use the subscribed endpoint."""
        self.login_as(self.journalist)
        response = self.client.get(reverse("api_subscribed_articles"))
        self.assertEqual(response.status_code, 403)


class CreateArticleTests(NewsTestCase):
    """Only journalists can create articles."""

    def test_journalist_can_create_article(self):
        """A journalist can create an unapproved article."""
        self.login_as(self.journalist)
        response = self.client.post(reverse("api_articles"), {
            "title": "Fresh story", "content": "Something happened.",
            "publisher": self.publisher.pk,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(title="Fresh story")
        self.assertEqual(article.author, self.journalist)
        # New articles must wait for an editor
        self.assertFalse(article.approved)

    def test_reader_cannot_create_article(self):
        """A reader cannot create an article."""
        self.login_as(self.reader)
        response = self.client.post(reverse("api_articles"), {
            "title": "Not allowed", "content": "No.",
        }, format="json")
        self.assertEqual(response.status_code, 403)


# Approval posts to /api/approved/ with requests, so requests.post is
# replaced with a mock and no real HTTP request is made
@mock.patch("news.utils.requests.post")
class ApproveArticleTests(NewsTestCase):
    """Editors approve. Approval emails subscribers and posts to
    /api/approved/."""

    def approve(self):
        """Send an approval request for the pending article."""
        url = reverse("api_article_detail", args=[self.pending_article.pk])
        return self.client.put(url, {"approved": True}, format="json")

    def test_editor_can_approve(self, mock_post):
        """Approval emails subscribers and posts to /api/approved/."""
        self.reader.subscribed_publishers.add(self.publisher)
        self.login_as(self.editor)

        response = self.approve()

        self.assertEqual(response.status_code, 200)
        self.pending_article.refresh_from_db()
        self.assertTrue(self.pending_article.approved)
        # The subscriber was emailed
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].bcc, ["reader@example.com"])
        # The article was posted to our own /api/approved/ endpoint
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], settings.APPROVED_API_URL)

    def test_journalist_cannot_approve(self, mock_post):
        """A journalist cannot approve an article."""
        self.login_as(self.journalist)
        response = self.approve()
        self.assertEqual(response.status_code, 403)
        self.pending_article.refresh_from_db()
        self.assertFalse(self.pending_article.approved)
        mock_post.assert_not_called()


class DeleteArticleTests(NewsTestCase):
    """Editors can delete articles, readers cannot."""

    def test_editor_can_delete(self):
        """An editor can delete an article."""
        self.login_as(self.editor)
        url = reverse("api_article_detail", args=[self.publisher_article.pk])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(
            Article.objects.filter(pk=self.publisher_article.pk).exists()
        )

    def test_reader_cannot_delete(self):
        """A reader cannot delete an article."""
        self.login_as(self.reader)
        url = reverse("api_article_detail", args=[self.other_article.pk])
        self.assertEqual(self.client.delete(url).status_code, 403)


class NewsletterTests(NewsTestCase):
    """Newsletters show approved articles and only journalists create
    them."""

    def setUp(self):
        """Add a newsletter with an approved and a pending article."""
        super().setUp()
        self.newsletter = Newsletter.objects.create(
            title="Weekly roundup", description="The best of the week.",
            author=self.journalist,
        )
        self.newsletter.articles.add(
            self.publisher_article, self.pending_article
        )

    def test_newsletter_shows_only_approved_articles(self):
        """A newsletter only lists approved articles."""
        self.login_as(self.reader)
        url = reverse("api_newsletter_detail", args=[self.newsletter.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        titles = [article["title"] for article in response.json()["articles"]]
        self.assertEqual(titles, ["Publisher news"])

    def test_reader_cannot_create_newsletter(self):
        """A reader cannot create a newsletter."""
        self.client.login(username="reader", password=PASSWORD)
        response = self.client.post(reverse("news:newsletter_create"), {
            "title": "Nope", "description": "",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Newsletter.objects.filter(title="Nope").exists())


class EditorScopeTests(NewsTestCase):
    """Editors only see articles of publishers they belong to."""

    def test_editor_only_sees_own_publishers_articles(self):
        """Editors do not see independent or other publishers' articles."""
        self.login_as(self.editor)
        response = self.client.get(reverse("api_articles"))
        titles = [article["title"] for article in response.json()]
        self.assertEqual(titles, ["Publisher news"])

        other_editor = User.objects.create_user(
            "other_editor", "e2@example.com", PASSWORD, role=User.EDITOR
        )
        self.login_as(other_editor)
        url = reverse("api_article_detail", args=[self.publisher_article.pk])
        self.assertEqual(self.client.get(url).status_code, 404)


@mock.patch("news.utils.requests.post")
class IndependentArticleTests(NewsTestCase):
    """Journalists publish their own independent articles."""

    def test_independent_article_is_published_on_save(self, mock_post):
        """An article with no publisher goes live and reaches subscribers."""
        self.reader.subscribed_journalists.add(self.journalist)
        self.login_as(self.journalist)
        response = self.client.post(reverse("api_articles"), {
            "title": "My own story", "content": "Written independently.",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["approved"])
        self.assertEqual(mail.outbox[0].bcc, ["reader@example.com"])
        mock_post.assert_called_once()


class PublisherTests(NewsTestCase):
    """Publishers register with a publication and choose its staff."""

    def test_publisher_registers_with_publication(self):
        """Registering as a publisher creates their publication."""
        response = self.client.post(reverse("news:register"), {
            "username": "owner", "email": "owner@example.com",
            "password": PASSWORD, "password_conf": PASSWORD,
            "role": "publisher", "publication_name": "Morning Star",
        })
        self.assertRedirects(response, reverse("news:my_publication"))
        owner = User.objects.get(username="owner")
        self.assertEqual(owner.publication.name, "Morning Star")
        self.assertTrue(owner.groups.filter(name="Publishers").exists())

    def test_publisher_assigns_editors_and_journalists(self):
        """A publisher adds an editor and a journalist to their
        publication."""
        owner = User.objects.create_user(
            "owner", "owner@example.com", PASSWORD, role=User.PUBLISHER
        )
        publication = Publisher.objects.create(
            name="Morning Star", owner=owner
        )
        self.client.login(username="owner", password=PASSWORD)
        self.client.post(reverse("news:my_publication"), {
            "editors": [self.editor.pk],
            "journalists": [self.other_journalist.pk],
        })
        self.assertIn(self.editor, publication.editors.all())
        self.assertIn(self.other_journalist, publication.journalists.all())
