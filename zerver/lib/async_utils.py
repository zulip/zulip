# nocoverage

import asyncio
import sys

from typing_extensions import override

if sys.version_info < (3, 14):

    class NoAutoCreateEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
        """
        By default asyncio.get_event_loop() automatically creates an event
        loop for the main thread if one isn't currently installed.  Since
        Django intentionally uninstalls the event loop within
        sync_to_async, that autocreation proliferates confusing extra
        event loops that will never be run.  It is also deprecated in
        Python 3.10.  This policy disables it so we don't rely on it by
        accident.
        """

        @override
        def get_event_loop(self) -> asyncio.AbstractEventLoop:
            return asyncio.get_running_loop()
