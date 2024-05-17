# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import importlib
import pkgutil
from typing import List, Optional

import zerver.worker
from zerver.worker.base import QueueProcessingWorker, test_queues, worker_classes


def get_worker(
    queue_name: str,
    *,
    threaded: bool = False,
    disable_timeout: bool = False,
    worker_num: Optional[int] = None,
) -> QueueProcessingWorker:
    if queue_name in {"test", "noop", "noop_batch"}:
        import_module = "zerver.worker.test"
    else:
        import_module = f"zerver.worker.{queue_name}"

    importlib.import_module(import_module)
    return worker_classes[queue_name](
        threaded=threaded, disable_timeout=disable_timeout, worker_num=worker_num
    )


def get_active_worker_queues(only_test_queues: bool = False) -> List[str]:
    """Returns all (either test, or real) worker queues."""
    for module_info in pkgutil.iter_modules(zerver.worker.__path__, "zerver.worker."):
        importlib.import_module(module_info.name)

    return [
        queue_name
        for queue_name in worker_classes
        if bool(queue_name in test_queues) == only_test_queues
    ]
