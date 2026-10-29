"""Forms for articles, newsletters, reader subscriptions and publications.
Largely reused from eCommerce task."""
from django import forms

from .models import Article, Newsletter, Publisher, User


class ArticleForm(forms.ModelForm):
    """Form for writing or editing an article."""

    class Meta:
        """Use the Article model and these fields."""

        model = Article
        fields = ["title", "content", "publisher"]

    def __init__(self, *args, journalist=None, allow_publisher=True,
                 **kwargs):
        """Limit the publishers to those the journalist belongs to.

        Editors edit with allow_publisher=False, because they cannot move
        an article to another publisher or make it independent.
        """
        super().__init__(*args, **kwargs)
        if not allow_publisher:
            del self.fields["publisher"]
            return
        # A journalist can only publish for publishers they belong to
        publisher_field = self.fields["publisher"]
        publisher_field.required = False  # optional for independents
        publisher_field.empty_label = "Independent (no publisher)"
        if journalist is not None:
            publisher_field.queryset = journalist.journalist_of.all()


class NewsletterForm(forms.ModelForm):
    """Form for creating or editing a newsletter of approved articles."""

    class Meta:
        """Use the Newsletter model and these fields."""

        model = Newsletter
        fields = ["title", "description", "articles"]
        widgets = {"articles": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        """Only offer approved articles for the newsletter."""
        super().__init__(*args, **kwargs)
        self.fields["articles"].queryset = Article.objects.filter(
            approved=True
        )


class SubscriptionForm(forms.ModelForm):
    """Form for a reader to choose their subscriptions."""

    class Meta:
        """Use the User model's subscription fields."""

        model = User
        fields = ["subscribed_publishers", "subscribed_journalists"]
        widgets = {
            "subscribed_publishers": forms.CheckboxSelectMultiple,
            "subscribed_journalists": forms.CheckboxSelectMultiple,
        }
        labels = {
            "subscribed_publishers": "Publishers",
            "subscribed_journalists": "Journalists",
        }

    def __init__(self, *args, **kwargs):
        """Only offer journalists in the journalist subscriptions."""
        super().__init__(*args, **kwargs)
        self.fields["subscribed_journalists"].queryset = User.objects.filter(
            role=User.JOURNALIST
        )


class PublicationForm(forms.ModelForm):
    """Form for a publisher to choose their editors and journalists."""

    class Meta:
        """Use the Publisher model's editors and journalists fields."""

        model = Publisher
        fields = ["editors", "journalists"]
        widgets = {
            "editors": forms.CheckboxSelectMultiple,
            "journalists": forms.CheckboxSelectMultiple,
        }
