# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import importlib
import pkgutil

from django.conf import settings

import zerver.worker
from zerver.worker.base import QueueProcessingWorker, test_queues, worker_classes


def get_worker(
    queue_name: str,
    *,
    threaded: bool = False,
    disable_timeout: bool = False,
    worker_num: int | None = None,
) -> QueueProcessingWorker:
    if queue_name in {"test", "noop", "noop_batch"}:
        import_module = "zerver.worker.test"
    else:
        import_module = f"zerver.worker.{queue_name}"

    importlib.import_module(import_module)
    return worker_classes[queue_name](
        threaded=threaded, disable_timeout=disable_timeout, worker_num=worker_num
    )


def get_active_worker_queues(only_test_queues: bool = False) -> list[str]:
    """Returns the worker queues that should run on this server, honoring
    configuration that gates a queue on a setting."""
    for module_info in pkgutil.iter_modules(zerver.worker.__path__, "zerver.worker."):
        importlib.import_module(module_info.name)

    queues = [
        queue_name
        for queue_name in worker_classes
        if bool(queue_name in test_queues) == only_test_queues
    ]
    if not settings.DEDICATED_SOFT_REACTIVATION_QUEUE:
        # Soft reactivations share the deferred_work queue unless a server
        # opts into a dedicated queue, so its worker is not run otherwise.
        queues = [queue_name for queue_name in queues if queue_name != "soft_reactivation"]
    return queues
