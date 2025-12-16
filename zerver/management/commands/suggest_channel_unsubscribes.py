from typing import Any
from django.conf import settings
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.actions.message_send import do_send_messages, internal_prep_private_message
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile, Subscription, Message, Realm
from zerver.models.users import get_system_bot

class Command(ZulipBaseCommand):
    help = """Suggests channel unsubscribes to users with high subscription counts."""

    @override
    def add_arguments(self, parser: Any) -> None:
        self.add_realm_args(parser)
        parser.add_argument(
            "--threshold",
            dest="threshold",
            type=int,
            default=30,
            help="Minimum number of subscriptions to trigger suggestion.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not send messages, just print what would happen.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        threshold = options["threshold"]
        dry_run = options["dry_run"]

        # If realm is not provided, process all realms
        if realm:
            realms = [realm]
        else:
            realms = Realm.objects.all()

        for realm in realms:
            self.process_realm(realm, threshold, dry_run)

    def process_realm(self, realm: Realm, threshold: int, dry_run: bool) -> None:
        # Get users with active subscriptions > threshold
        users_with_high_subs = (
            UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False)
            .annotate(sub_count=Count("subscription", filter=Q(subscription__active=True)))
            .filter(sub_count__gt=threshold)
        )

        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, realm.id)

        count = 0
        for user in users_with_high_subs:
            # Check if we already sent a suggestion recently?
            # For now, let's just check if they EVER received this specific message pattern.
            # In a real impl, we might store state in a model to avoid spamming.
            # But adhering to the constraints of "no database migrations", we'll check message history carefully or just assume this cron runs infrequently.
            # Actually, let's check if they received a message from notification-bot with the specific link recently?
            # To keep it simple and efficient without DB changes: checking for existence of ANY link to #channels/recommendations from notification bot in DM.
            
            # This check is expensive if done naively. 
            # Ideally we'd have a UserHotspot or similar. 
            # Constraint: "Modify only the necessary files — do not change unrelated code or introduce breaking changes." "No database migrations".
            # So I cannot add a new UserHotspot.
            # I will assume for this MVP that the command is run once or manually.
            # OR I can check last message from notification bot?
            
            # Let's simple check if they have received a message with the recommendation link.
            # This might be slow but it's a management command.
            
            already_notified = Message.objects.filter(
                sender=notification_bot,
                recipient__type=1, # Recipient.PERSONAL
                recipient__type_id=user.id, # This is wrong, Recipient.id is not user.id
                content__contains="#channels/recommendations"
            ).exists()
            
            # Wait, accessing recipient via user profile is better.
            # user.recipient_id
            if Message.objects.filter(
                sender=notification_bot,
                recipient_id=user.recipient_id,
                content__contains="#channels/recommendations"
            ).exists():
                continue

            count += 1
            if dry_run:
                print(f"Would send suggestion to {user.delivery_email} (Subs: {user.sub_count})")
            else:
                self.send_suggestion(user, notification_bot, user.sub_count)
        
        if dry_run:
            print(f"Total users to suggest in realm {realm.string_id}: {count}")

    def send_suggestion(self, user: UserProfile, bot: UserProfile, sub_count: int) -> None:
        content = _(
            "You are currently subscribed to {sub_count} channels. "
            "To help focus on what's important, we can suggest some channels to unsubscribe from or mute.\n\n"
            "[Review recommendations](#channels/recommendations)"
        ).format(sub_count=sub_count)

        internal_send_private_message(
            realm=user.realm,
            sender=bot,
            recipient=user,
            content=content
        )

def internal_send_private_message(realm: Realm, sender: UserProfile, recipient: UserProfile, content: str) -> None:
    # Helper similar to zerver.lib.onboarding but using do_send_messages
    messages = [
        internal_prep_private_message(
            realm=realm,
            sender=sender,
            recipient=recipient,
            content=content
        )
    ]
    do_send_messages(messages)
