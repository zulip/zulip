# Translation guidelines

Zulip has full support for Unicode (and partial support for RTL
languages), so you can use your preferred language everywhere in
Zulip.

Additionally, the Zulip UI is translated into more than a dozen major
languages, including Spanish, German, Hindi, French, Chinese, Russian,
and Japanese, and we're always excited to add more. If you speak a
language other than English, your help with translating Zulip would be
greatly appreciated!

If you are interested in knowing about the technical end-to-end
tooling and processes for tagging strings for translation and syncing
translations in Zulip, read about [Internationalization for
Developers](internationalization.md).

## Translators' workflow

These are the steps you should follow if you want to help translate
Zulip:

1. Join [#translation][translation-channel] in the [Zulip development
   community server](https://zulip.com/development-community/), and say hello.
   That channel is also the right place for any questions, updates on your
   progress, reporting problematic strings, etc.

1. [Sign up for Weblate](https://hosted.weblate.org/accounts/register/).

   :::{note}
   Unless you plan to contribute country-specific translations, do not
   select a country-specific language in the **Languages** list when
   you sign up. E.g., use **English (United Kingdom) (en_GB)** if you
   plan to translate Zulip into UK English, but select **Spanish
   (es)** rather than **Spanish (Colombia) (es_CO)** for general
   Spanish translations.
   :::

1. Navigate to the [Zulip project on Weblate](https://hosted.weblate.org/projects/zulip/).

1. Choose the language you'd like to translate into; your preferred
   languages should be at the top.

1. Optionally, use the "Components" tab at the top to translate only
   part of the project. Zulip has several different components, split
   up by where they are used:

   - `Flutter` is used for the mobile app.
   - `Desktop` is for the parts of the Zulip desktop apps that are not
     shared with the Zulip web app. This is a fairly small number of
     strings.
   - `Django` and `Frontend` have strings for the next major release
     of the Zulip server and web app (which is what we run on
     chat.zulip.org and Zulip Cloud).
   - The variants of `Django` and `Frontend` with names
     ending with a version, like `(10.x)`, are strings for Zulip's
     current [stable release series](../overview/release-lifecycle.md).

   Weblate is smart about only asking you to translate a string once
   even if it appears in multiple resources. The `(10.x)` type variants
   allow translators to get a language to 100% translated for the
   current release.

1. Click the "Translate" button to begin translating. Refer to
   [Weblate's
   documentation](https://docs.weblate.org/en/latest/user/translating.html#translating)
   for how to translate each string.

1. If possible, test your translations (details below).

1. Ask in Zulip for a maintainer to merge the strings from Weblate,
   and deploy the update to chat.zulip.org so you can verify them in
   action there.

Some useful tips for your translating journey:

- Follow your language's [translation guide](#translation-style-guides).
  Keeping it open in a tab while translating is very handy. If one
  doesn't exist one, write one as you go; they're easiest to write as
  you go along and will help any future translators a lot.

- Use, and update, the [Weblate
  glossary](https://hosted.weblate.org/projects/zulip/glossary/) for
  your language. This will help by providing consistent, inline
  translation references for terms (e.g., "channel") which are used
  repeatedly throughout the application.

- Don't translate variables or code (usually preceded by a `%`, inside
  HTML tags `<...>`, or enclosed in braces like `{variable}`); just
  keep them verbatim.

- When context is unclear, you may find it helpful to follow the
  "Source string location" link in the right sidebar of the Weblate
  UI.

- When in doubt, ask for context in
  [#translation](https://chat.zulip.org/#narrow/channel/58-translation) in
  the [Zulip development community server](https://zulip.com/development-community/).

- Pay attention to capital letters and punctuation. Details make the
  difference! Weblate will catch, and warn about, some cases of
  mismatched punctuation.

- Take advantage of Weblate's [key
  bindings](https://docs.weblate.org/en/latest/user/translating.html#keyboard-shortcuts)
  for efficiency.

- While one should definitely prioritize translating the `Frontend`
  and `Flutter` components, since the most prominent user-facing
  strings are there, API error messages in `Django` are presented to
  users, so a full translation should include them.

### Testing translations

This section assumes you have a
[Zulip development environment](../development/overview.md) set up;
if setting one up is a problem for you, ask in chat.zulip.org and we
can usually just deploy the latest translations there.

1. Add the Weblate remote to your Git repository:

   ```shell
   git remote add weblate https://hosted.weblate.org/git/zulip/django/
   ```

1. Merge the changes into your local repository:

   ```shell
   git cherry-pick weblate/main ^upstream/main
   ```

There are a few ways to see your translations in the Zulip UI:

- You can insert the language code as a URL prefix. For example, you
  can view the login page in German using
  `http://localhost:9991/de/login/`. This works for any part of the
  Zulip UI, including portico (logged-out) pages.
- For Zulip's logged-in UI (i.e. the actual web app), you can [pick the
  language](https://zulip.com/help/change-your-language) in the
  Zulip UI.
- If your system has languages configured in your OS/browser, Zulip's
  portico (logged-out) pages will automatically use your configured
  language. Note that we only tag for translation strings in pages
  that individual users need to use (e.g., `/login/`, `/register/`,
  etc.), not marketing pages like `/features/`.
- In case you need to understand how the above interact, Zulip figures
  out the language the user requests in a browser using the following
  prioritization (mostly copied from the Django docs):

  1. It looks for the language code as a URL prefix (e.g., `/de/login/`).
  1. It looks for the cookie named 'django_language'. You can set a
     different name through the `LANGUAGE_COOKIE_NAME` setting.
  1. It looks for the `Accept-Language` HTTP header in the HTTP request
     (this is how browsers tell Zulip about the OS/browser language).

- Using an HTTP client library like `requests`, `cURL` or `urllib`,
  you can pass the `Accept-Language` header; here is some sample code to
  test `Accept-Language` header using Python and `requests`:

  ```python
  import requests
  headers = {"Accept-Language": "de"}
  response = requests.get("http://localhost:9991/login/", headers=headers)
  print(response.content)
  ```

  This can occasionally be useful for debugging.

### Machine translation

Weblate has [built-in machine translation
capabilities](https://docs.weblate.org/en/latest/admin/machine.html).
If machine translation is enabled for your language, you can generate one by
clicking the **Automatic suggestions** tab below the translation box.

Bear in mind that we expect human-quality translations for
Zulip. While machine translation can be a helpful aid, please be sure
to review all machine translated strings.

### Translation style guides

We maintain translation style guides for Zulip, giving guidance on how
Zulip should be translated into specific languages (e.g., what word to
translate words like "channel" to), with reasoning, so that future
translators can understand and preserve those decisions:

- [Chinese](chinese.md)
- [Finnish](finnish.md)
- [French](french.md)
- [German](german.md)
- [Hindi](hindi.md)
- [Japanese](japanese.md)
- [Polish](polish.md)
- [Russian](russian.md)
- [Spanish](spanish.md)

We encourage this information to also be placed in [Weblate's
glossary](https://hosted.weblate.org/projects/zulip/glossary/), which
will help provide inline suggestions when translating.

Some translated languages don't have these, but we highly encourage
translators for new languages (or those updating a language) write a
style guide as they work, since it's easy to take notes as you
translate, and doing so greatly increases the ability of future
translators to update the translations in a consistent way. See [our
docs on this documentation](../documentation/overview.md) for how to
submit your changes.

### Capitalization

We expect that all the English translatable strings in Zulip are
properly capitalized in a way consistent with how Zulip does
capitalization in general. This means that:

- The first letter of a sentence or phrase should be capitalized.
  - Correct: "Channel settings"
  - Incorrect: "Channel Settings"
- All proper nouns should be capitalized.
  - Correct: "This is Zulip"
  - Incorrect: "This is zulip"
- All common words like URL, HTTP, etc. should be written in their
  standard forms.
  - Correct: "URL"
  - Incorrect: "Url"

The Zulip test suite enforces these capitalization guidelines in the
web app codebase [in our test
suite](../testing/testing.md#other-test-suites)
(`./tools/check-capitalization`; `tools/lib/capitalization.py` has
some exclude lists, e.g., `IGNORED_PHRASES`).

[translation-channel]: https://chat.zulip.org/#narrow/channel/58-translation
