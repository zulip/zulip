
from argparse import ArgumentParser
from typing import Any, List

from zerver.lib.actions import bulk_add_subscriptions, \
    bulk_remove_subscriptions, do_deactivate_stream
from zerver.lib.cache import cache_delete_many, to_dict_cache_key_id
from zerver.lib.management import ZulipBaseCommand
from zerver.models import Message, Subscription, \
    get_stream, get_stream_recipient

def bulk_delete_cache_keys(message_ids_to_clear: List[int]) -> None:
    while len(message_ids_to_clear) > 0:
        batch = message_ids_to_clear[0:5000]

        keys_to_delete = [to_dict_cache_key_id(message_id) for message_id in batch]
        cache_delete_many(keys_to_delete)

        message_ids_to_clear = message_ids_to_clear[5000:]

class Command(ZulipBaseCommand):
    help = """Merge two streams."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('stream_to_keep', type=str,
                            help='name of stream to keep')
        parser.add_argument('stream_to_destroy', type=str,
                            help='name of stream to merge into the stream being kept')
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser
        stream_to_keep = get_stream(options["stream_to_keep"], realm)
        stream_to_destroy = get_stream(options["stream_to_destroy"], realm)

        recipient_to_destroy = get_stream_recipient(stream_to_destroy.id)
        recipient_to_keep = get_stream_recipient(stream_to_keep.id)

        # The high-level approach here is to move all the messages to
        # the surviving stream, deactivate all the subscriptions on
        # the stream to be removed and deactivate the stream, and add
        # new subscriptions to the stream to keep for any users who
        # were only on the now-deactivated stream.

        # Move the messages, and delete the old copies from caches.
        message_ids_to_clear = list(Message.objects.filter(
            recipient=recipient_to_destroy).values_list("id", flat=True))
        count = Message.objects.filter(recipient=recipient_to_destroy).update(recipient=recipient_to_keep)
        print("Moved %s messages" % (count,))
        bulk_delete_cache_keys(message_ids_to_clear)

        # Move the Subscription objects.  This algorithm doesn't
        # preserve any stream settings/colors/etc. from the stream
        # being destroyed, but it's convenient.
        existing_subs = Subscription.objects.filter(recipient=recipient_to_keep)
        users_already_subscribed = dict((sub.user_profile_id, sub.active) for sub in existing_subs)

        subs_to_deactivate = Subscription.objects.filter(recipient=recipient_to_destroy, active=True)
        users_to_activate = [
            sub.user_profile for sub in subs_to_deactivate
            if not users_already_subscribed.get(sub.user_profile_id, False)
        ]

        if len(subs_to_deactivate) > 0:
            print("Deactivating %s subscriptions" % (len(subs_to_deactivate),))
            bulk_remove_subscriptions([sub.user_profile for sub in subs_to_deactivate],
                                      [stream_to_destroy],
                                      self.get_client())
        do_deactivate_stream(stream_to_destroy)
        if len(users_to_activate) > 0:
            print("Adding %s subscriptions" % (len(users_to_activate),))
            bulk_add_subscriptions([stream_to_keep], users_to_activate)
