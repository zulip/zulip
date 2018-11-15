# Upgrading Django

This article documents notes on the process for upgrading Zulip to
new major versions of Django.  Here are the steps:

* Carefully read the Django upstream changelog, and `git grep` to
  check if we're using anything deprecated or significantly modified
  and put them in an issue (and then starting working through them).
  Also, note any new features we might want to use after the upgrade,
  and open an issue listing them;
  [example](https://github.com/zulip/zulip/issues/2564).
* Start submitting PRs to do any deprecation-type migrations that work
  on both the old and new version of Django.  The goal here is to have
  the actual cutover commit be as small as possible, and to test as
  much of the changes for the migration as we can independently from
  the big cutover.
* Check the version support of the third-party Django packages we use
  (`git grep django requirements/` to see a list), upgrade any as
  needed and file bugs upstream for any that lack support.  Look into
  fixing said bugs.
* Look at the pieces of Django code that we've copied and then
  adapted, and confirm whether Django has any updates to the modified
  code we should apply.  Partial list:
  * SessionMiddleware in `django.contrib.sessions.middleware` (we fork `get_response`).
  * `CursorDebugWrapper`, which we have a modified version of in
    `zerver/lib/db.py`.  See
    [the issue for contributing this upstream](https://github.com/zulip/zulip/issues/974)
  * `PasswordResetForm` and any other forms we import from
    `django.contrib.auth.forms` in `zerver/forms.py` (which has all of
    our Django forms).
  * `AsyncDjangoHandlerBase` in `zerver/tornado/handlers.py` is a very
    small patch on `base.BaseHandler`; see the comments with `BY
    ZULIP` for our changes (unfortunately now more different due to
    style differences and mypy annotations).  This configurability
    should also be contributed to Django upstream.
