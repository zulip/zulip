"""
Management command to seed the dev Zulip instance with realistic unread
messages so the catch-up / AI-summary feature can be tested end-to-end
with real Claude context linking.

Usage (inside Vagrant):
    python manage.py populate_catchup_messages --realm zulip
    python manage.py populate_catchup_messages --realm zulip --reader hamlet@zulip.com

The command:
  1. Ensures the required streams exist (creating them if needed).
  2. Subscribes all participant users to those streams.
  3. Sends a set of realistic messages across several topics as various users.
  4. Does NOT mark the messages as read for the --reader user, so they show
     up as unread in the catch-up view.
"""

from typing import Any

from django.core.management.base import CommandParser
from typing_extensions import override

from zerver.actions.message_send import internal_send_stream_message
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import ensure_stream
from zerver.models import UserProfile


# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------
#
# Each entry is:
#   (sender_email, stream_name, topic_name, content)
#
# The messages form coherent conversations that give Claude enough material
# to produce a structured summary with meaningful action items and context
# links.

MESSAGES = [
    # ── Stream: devel · Topic: Auth middleware refactor ──────────────────────
    (
        "iago@zulip.com",
        "devel",
        "Auth middleware refactor",
        "Started the auth middleware refactor. Moving session token storage "
        "from cookies to an encrypted DB column to meet the new SOC-2 "
        "compliance requirement. PR is at #1847.",
    ),
    (
        "cordelia@zulip.com",
        "devel",
        "Auth middleware refactor",
        "Reviewed the PR. The encryption key rotation logic looks off — "
        "if the key changes mid-session the user gets a 500. Can you add a "
        "graceful fallback that logs out cleanly instead?",
    ),
    (
        "iago@zulip.com",
        "devel",
        "Auth middleware refactor",
        "Good catch. I'll add a try/except that catches `InvalidToken`, "
        "clears the session, and redirects to login. Also updating the "
        "migration to backfill existing sessions.",
    ),
    (
        "hamlet@zulip.com",
        "devel",
        "Auth middleware refactor",
        "@**Cordelia, Lear's daughter** can you re-review once Iago pushes "
        "the fallback fix? We need this merged before Friday's release cut.",
    ),
    (
        "cordelia@zulip.com",
        "devel",
        "Auth middleware refactor",
        "Will do. Also — don't forget to update the `SESSION_COOKIE_SECURE` "
        "setting in prod_settings_template. Currently it defaults to False.",
    ),

    # ── Stream: devel · Topic: NLP pipeline performance ──────────────────────
    (
        "prospero@zulip.com",
        "devel",
        "NLP pipeline performance",
        "The nightly benchmark run shows the TF-IDF summarizer is taking "
        "~4 s per topic on the p99 case (300-message topics). We should "
        "look at caching the IDF corpus between requests.",
    ),
    (
        "hamlet@zulip.com",
        "devel",
        "NLP pipeline performance",
        "Agreed. We already pickle the corpus on disk — maybe just load it "
        "once at module level rather than on every request?",
    ),
    (
        "prospero@zulip.com",
        "devel",
        "NLP pipeline performance",
        "Done. Moved the corpus load into a module-level singleton. P99 "
        "latency dropped from 4 s to 280 ms. Will open a PR today.",
    ),
    (
        "iago@zulip.com",
        "devel",
        "NLP pipeline performance",
        "@**all** please review the perf PR before EOD — it unblocks the "
        "catch-up feature demo scheduled for Thursday.",
    ),

    # ── Stream: devel · Topic: CI/CD pipeline update ─────────────────────────
    (
        "cordelia@zulip.com",
        "devel",
        "CI/CD pipeline update",
        "Added a new GitHub Actions workflow `nlp-tests.yml` that runs the "
        "NLP test suite on every PR targeting `main`. It uses the cached "
        "corpus so it should complete in under 2 minutes.",
    ),
    (
        "hamlet@zulip.com",
        "devel",
        "CI/CD pipeline update",
        "Looks good. One thing — the workflow needs the `ANTHROPIC_API_KEY` "
        "secret added to the repo settings so the integration tests can call "
        "Claude. I'll add it now.",
    ),
    (
        "prospero@zulip.com",
        "devel",
        "CI/CD pipeline update",
        "Also add `LITELLM_MODEL` to the secrets — the integration test "
        "reads that env var to know which model to use.",
    ),
    (
        "cordelia@zulip.com",
        "devel",
        "CI/CD pipeline update",
        "Done — both secrets added. The first run passed ✅. "
        "Merging the workflow PR now.",
    ),

    # ── Stream: backend · Topic: Catch-up endpoint design ────────────────────
    (
        "iago@zulip.com",
        "backend",
        "Catch-up endpoint design",
        "RFC: The `/json/catch-up/summary` endpoint currently fetches up to "
        "200 unread messages. Should we paginate or just hard-cap and let "
        "Claude handle the truncation?",
    ),
    (
        "hamlet@zulip.com",
        "backend",
        "Catch-up endpoint design",
        "Hard-cap for now. Claude's 200k context window is plenty for 200 "
        "messages. We can revisit if users report missing important context.",
    ),
    (
        "prospero@zulip.com",
        "backend",
        "Catch-up endpoint design",
        "We should also add a `since` parameter so power users can narrow "
        "to a specific time window (e.g. last 8 hours instead of all unread).",
    ),
    (
        "iago@zulip.com",
        "backend",
        "Catch-up endpoint design",
        "@**Hamlet** can you create a ticket for the `since` parameter? "
        "Out of scope for this sprint but worth tracking.",
    ),

    # ── Stream: backend · Topic: Rate limiting for AI calls ──────────────────
    (
        "cordelia@zulip.com",
        "backend",
        "Rate limiting for AI calls",
        "We need a per-user rate limit on the catch-up summary endpoint. "
        "Suggested: max 10 calls/hour per user to keep API costs down.",
    ),
    (
        "hamlet@zulip.com",
        "backend",
        "Rate limiting for AI calls",
        "10/hour might be too low for heavy users — maybe 30/hour with "
        "a daily cap of $1 per user (tracked via the existing cost table)?",
    ),
    (
        "iago@zulip.com",
        "backend",
        "Rate limiting for AI calls",
        "The `MAX_PER_USER_MONTHLY_AI_COST` setting already handles the "
        "monthly budget. Let's add the 30/hour limit on top and see if "
        "anyone hits it in the beta.",
    ),

    # ── Stream: frontend · Topic: Catch-up UI polish ─────────────────────────
    (
        "cordelia@zulip.com",
        "frontend",
        "Catch-up UI polish",
        "The AI Summary panel looks great but the keyword pills overflow on "
        "mobile (< 400px). Suggest adding `flex-wrap: wrap` to the pill "
        "container.",
    ),
    (
        "hamlet@zulip.com",
        "frontend",
        "Catch-up UI polish",
        "Fixed in the latest commit. Also bumped the font size of topic "
        "card titles from 13px to 14px — easier to scan.",
    ),
    (
        "prospero@zulip.com",
        "frontend",
        "Catch-up UI polish",
        "The 'Open conversation ↗' link in each card should open in the "
        "same tab (current behaviour) — good. But the 'Jump ↗' links in "
        "the summary panel navigate away without any confirmation. "
        "Should we warn users they're leaving the catch-up view?",
    ),
    (
        "cordelia@zulip.com",
        "frontend",
        "Catch-up UI polish",
        "No warning — the current flow (hide panel → navigate) is snappy "
        "and expected. Users can just hit Back or re-open catch-up. "
        "Let's keep it simple.",
    ),
]


class Command(ZulipBaseCommand):
    help = (
        "Seed the dev Zulip instance with realistic messages for testing "
        "the catch-up / AI-summary feature."
    )

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument(
            "--reader",
            default="desdemona@zulip.com",
            help=(
                "Email of the user who should see these messages as UNREAD "
                "(default: desdemona@zulip.com). Log in as this user to test "
                "the catch-up view."
            ),
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None

        reader_email: str = options["reader"]
        try:
            reader = UserProfile.objects.get(realm=realm, delivery_email=reader_email)
        except UserProfile.DoesNotExist:
            self.stderr.write(f"Reader user {reader_email!r} not found in realm.")
            return

        # Collect all unique (sender, stream) pairs so we can subscribe them
        stream_names: set[str] = {m[1] for m in MESSAGES}
        sender_emails: set[str] = {m[0] for m in MESSAGES}

        # Ensure all senders exist
        senders: dict[str, UserProfile] = {}
        for email in sender_emails:
            try:
                senders[email] = UserProfile.objects.get(realm=realm, delivery_email=email)
            except UserProfile.DoesNotExist:
                self.stderr.write(f"Sender {email!r} not found — skipping their messages.")

        # Ensure streams exist and subscribe everyone (including reader)
        streams: dict[str, Any] = {}
        all_users = list(senders.values()) + [reader]
        for name in stream_names:
            stream = ensure_stream(realm, name, acting_user=None)
            streams[name] = stream
            bulk_add_subscriptions(realm, [stream], all_users, acting_user=None)
            self.stdout.write(f"  Stream #{name} ready.")

        # Send messages — they will be UNREAD for `reader` because we don't
        # pass mark_as_read_for_acting_user=True for the reader.
        count = 0
        for sender_email, stream_name, topic_name, content in MESSAGES:
            if sender_email not in senders:
                continue
            sender = senders[sender_email]
            stream = streams[stream_name]
            msg_id = internal_send_stream_message(
                sender=sender,
                stream=stream,
                topic_name=topic_name,
                content=content,
                mark_as_read_for_acting_user=True,  # mark as read for sender only
                acting_user=sender,
            )
            if msg_id is not None:
                count += 1
                self.stdout.write(
                    f"  [{count:02d}] #{stream_name} > {topic_name!r} "
                    f"(id={msg_id}, from {sender_email})"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Sent {count} messages across {len(stream_names)} streams.\n"
                f"Log in as {reader_email} and open the Catch-up view to test.\n"
            )
        )
