# Planning: News Application

## 1. Overview

A Django news application. Journalists write articles for publishers (which
are reviewed, approved and posted by the publishers' Editors) or publish
independent articles of their own. Publishers choose their own editors and
journalists. Readers subscribe to publishers and journalists, read approved
articles and newsletters, and receive approved articles by email. A RESTful
API gives third-party clients the articles (protected by token
authentication).

## 2. Functional requirements

A lot of code can be reused from previous tasks to save time and ensure
consistency. This will also help ensure minimal rearchitecting and
troubleshooting.

**All users**
1. Register as a Reader, a Journalist, an Editor or a Publisher, log in and
   log out. Users confirm their password when registering, and each email
   address can only be used for one account. Publishers also enter the name
   of their publication.
2. View approved articles and newsletters (editors: see below).

**Publishers**

3. Choose the editors and journalists who work for their publication on a
   "My publication" page.

**Readers**

4. Subscribe to publishers and journalists on a "My subscriptions" page.
5. Receive an email when an article from a subscription is approved.
6. Retrieve articles from their subscriptions through the API.

**Journalists**

7. Create, view, edit and delete their own articles. Articles for a
   publisher wait for approval by one of its editors. Independent articles
   (no publisher) are published as soon as they are saved.
8. Create, view, edit and delete their own newsletters.
9. Create articles through the API.

**Editors**

10. Review articles of their publishers that are waiting for approval,
    and approve them.
11. On approval, the article is emailed to the subscribers of its journalist
    and publisher, and posted to the project's own `/api/approved/` endpoint.
12. View, edit and delete articles of their publishers, and the
    newsletters of their publishers' journalists, on the website and through
    the API. Editors only see their own publishers' content. To read
    everything else, they register a separate Reader account.

**API**

13. Token endpoint: `POST /api/token/`.
14. `GET /api/articles/`, `GET /api/articles/subscribed/`,
    `GET /api/articles/<id>/`, `POST /api/articles/`,
    `PUT /api/articles/<id>/`, `DELETE /api/articles/<id>/`.
15. `POST /api/approved/` to log approved articles.
16. Read-only newsletters: `GET /api/newsletters/` and
    `GET /api/newsletters/<id>/`.

**Security**
- Passwords are hashed and checked with Django's validators.
- Every page and endpoint needs a logged-in user.
- Each action checks the user's role and group permissions.
- Forms use CSRF tokens.
- Passwords & keys are kept in a `.env` file that is not committed.

## 3. Roles, groups and permissions

See `diagrams/use_case_diagram.png` for what each role can do.

Saving a user puts them in the group that matches their role. The groups are
created with their permissions when migrations run.

| Role | Group | Articles | Newsletters |
|------|-------|----------|-------------|
| Reader | Readers | view | view |
| Editor | Editors | view, change, delete | view, change, delete |
| Journalist | Journalists | add, view, change, delete | add, view, change, delete |
| Publisher | Publishers | view | view (plus view and change publisher) |

Extra rules on top of the permissions:
- Journalists can only change or delete their own articles and newsletters.
- Editors can only see, change or delete articles of publishers they
  belong to, and newsletters written by those publishers' journalists. Any
  other article or newsletter gives a 404. There is no new field for this:
  a newsletter's publisher comes from its author.
- Only editors can approve articles (only for their own publishers).
  Editors cannot move an article to a different publisher.
- Publishers can only change their own publication (editors and
  journalists).
- Only readers have subscriptions. If a user's role is not Reader, their
  subscriptions are cleared, and the journalist-only fields return `None` for
  anyone who is not a journalist.

## 4. Data design

See `diagrams/class_diagram.png`.

| Table | Data | Links |
|-------|-------|-------|
| User | username, email, password, role (reader, journalist, editor or publisher) | groups; subscribed publishers; subscribed journalists |
| Publisher | name | owner (the publisher user), editors, journalists (users) |
| Article | title, content, created_at, approved | author (user), publisher (optional) |
| Newsletter | title, description, created_at | author (user), articles |

## 5. User interface

Every page extends `base.html`, which loads the shared stylesheet
(`news/static/news/styles.css`) and has a navigation bar that changes with
the user's role. As well as any success or error messages.

| Page | Who | Contents |
|------|-----|----------|
| Login, Register | Everyone | Simple forms. Register has Reader, Journalist, Editor or Publisher, a publication name (publishers only) and a confirm password field. |
| Articles | Everyone | Approved articles. With author, publisher and date. Editors see their publishers' articles only. |
| Article | Everyone | Full article. Edit and delete links for author and editors. |
| Newsletters, Newsletter | Everyone | Newsletters and approved articles. |
| My subscriptions | Readers | Tick boxes for publishers and journalists. |
| My articles | Journalists | Own articles with "awaiting approval", "approved" or "published" (independent) status. |
| Write an article, Create a newsletter | Journalists | Forms. Publishers limited to their own. |
| Review articles | Editors | Their publishers' articles awaiting approval. Each has approve button. |
| My publication | Publishers | Tick boxes for the editors and journalists of their publication. |

## 6. API design

- **Representation:** JSON, using Django REST framework serialisers for
  Article, User, Newsletter and Publisher. An article shows its author (ID,
  username and role) and its publisher (ID and name).
- **Authentication:** Django REST framework token authentication. Clients get
  a token from `POST /api/token/` and send `Authorization: Token <token>`.
- **Endpoints:** nouns for resources and HTTP methods for actions!!

| Method | Endpoint | Allowed |
|--------|----------|---------|
| POST | `/api/token/` | Anyone with a valid username and password |
| GET | `/api/articles/` | All logged-in users (approved articles only; editors get their publishers' articles only) |
| GET | `/api/articles/subscribed/` | Readers |
| GET | `/api/articles/<id>/` | All (unapproved only for its author and its publisher's editors; editors only their publishers' articles) |
| POST | `/api/articles/` | Journalists |
| PUT | `/api/articles/<id>/` | The publisher's editors, or the journalist who wrote it. Only editors can send `approved`. |
| DELETE | `/api/articles/<id>/` | The publisher's editors, or the journalist who wrote it |
| POST | `/api/approved/` | Editors and journalists (called by the app when an article is published) |
| GET | `/api/newsletters/`, `/api/newsletters/<id>/` | All logged-in users (editors: their publishers' journalists' newsletters only) |

## 7. Approval (Option 2, without signals)

Approval is handled in code called from the approval views, not with signals.
The editor's approve page and the API's `PUT` both call one helper,
`approve_article()` in `news/utils.py`. Independent articles have no editor,
so they are approved by the same helper as soon as the journalist saves them
(`update_article_status()` in `news/utils.py`). `approve_article()`:

1. sets `approved` to true and saves the article,
2. emails the article to readers subscribed to its journalist or publisher
   (as BCC, so readers cannot see each other - POPIA is a thing), and
3. posts the article as JSON to `/api/approved/` with the `requests` module,
   using the token of the user who approved (or published) it. The endpoint
   logs it.

If a journalist later moves a published article to a different publisher
(for example, an independent article to a publisher), it goes back to
"awaiting approval" so that publisher's editors can review it.

See `diagrams/sequence_approval.png` and `diagrams/sequence_api.png`.

## 8. Failure handling

| What goes wrong | What happens |
|-----------------|--------------|
| Not logged in (website) | Redirected to the login page |
| No or invalid token (API) | 401 Unauthorized |
| Wrong role or not the owner | 403 page or `{"error": ...}` |
| Article or newsletter does not exist, or is unapproved for a reader | 404 |
| Missing or invalid fields | The form is shown again, or 400 with the field errors |
| Journalist chooses a publisher they do not belong to | 403 |
| Editor opens an article or newsletter outside their publishers | 404 |
| Editor not yet added to a publisher | Articles, newsletters and review pages show "A publisher needs to add you before you can see and review articles." |
| Editor tries to change an article's publisher through the API | 403 |
| Email cannot be sent | Error logged, approval kept |
| `/api/approved/` cannot be reached | Error logged, approval kept |
| Username taken, empty fields or weak password on registration | Register page shows the error |
| Passwords do not match on registration | Register page shows "Passwords do not match." |
| Email address already used by another account | Register page shows the error |
| Publisher registers without a publication name, or with a name already taken | Register page shows the error |

## 9. Testing

`news/tests.py` use Django's test framework and Django REST framework's
`APIClient` with tokens. It covers:
- token login and access for each role
- readers getting only their subscribed content
- journalists creating articles, and independent articles being published
  on save
- editors approving and deleting, and only seeing their publishers' articles
- publishers registering with a publication and choosing its editors and
  journalists
- newsletters on the API and website
- the approval logic, with `requests.post` mocked and the email checked in
  Django's test outbox

(Each area to include both successful and failed requests, as per brief.)
