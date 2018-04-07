import mock
import os
from typing import Any
import ujson

from pika.exceptions import ConnectionClosed

from zerver.lib.queue import TornadoQueueClient
from zerver.lib.test_classes import ZulipTestCase

class TestTornadoQueueClient(ZulipTestCase):
    @mock.patch('zerver.lib.queue.logging.getLogger', autospec=True)
    @mock.patch('zerver.lib.queue.ExceptionFreeTornadoConnection', autospec=True)
    def test_on_open_closed(self, mock_cxn: mock.MagicMock,
                            mock_get_logger: mock.MagicMock) -> None:
        connection = TornadoQueueClient()
        connection.connection.channel.side_effect = ConnectionClosed
        connection._on_open(mock.MagicMock())
