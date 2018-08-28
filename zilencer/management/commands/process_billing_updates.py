"""\
Run BillingProcessors.

This management command is run via supervisor. Do not run on multiple
machines, as the code has not been made robust to race conditions from doing
so.  (Alternatively, you can set `BILLING_PROCESSOR_ENABLED=False` on all but
one machine to make the command have no effect.)
"""

import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from zerver.lib.context_managers import lockfile
from zerver.lib.management import sleep_forever
from zilencer.lib.stripe import StripeConnectionError, \
    run_billing_processor_one_step
from zilencer.models import BillingProcessor

class Command(BaseCommand):
    help = """Run BillingProcessors, to sync billing-relevant updates into Stripe.

Run this command under supervisor.

Usage: ./manage.py process_billing_updates
"""

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.BILLING_PROCESSOR_ENABLED:
            sleep_forever()

        with lockfile("/tmp/zulip_billing_processor.lockfile"):
            while True:
                for processor in BillingProcessor.objects.exclude(
                        state=BillingProcessor.STALLED):
                    try:
                        entry_processed = run_billing_processor_one_step(processor)
                    except StripeConnectionError:
                        time.sleep(5*60)
                    # Less load on the db during times of activity
                    # and more responsiveness when the load is low
                    if entry_processed:
                        time.sleep(10)
                    else:
                        time.sleep(2)
