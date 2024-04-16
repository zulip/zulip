import itertools
import logging
import re
import sys
from contextlib import contextmanager
from io import SEEK_SET, TextIOWrapper
from types import TracebackType
from typing import IO, TYPE_CHECKING, Iterable, Iterator, List, Optional, Type

from typing_extensions import override

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer


class ExtraConsoleOutputInTestError(Exception):
    pass


class ExtraConsoleOutputFinder:
    def __init__(self) -> None:
        valid_line_patterns = [
            # Example: Running zerver.tests.test_attachments.AttachmentsTests.test_delete_unauthenticated
            rb"^Running ",
            rb"^----------------------------------------------------------------------",
            # Example: INFO: URL coverage report is in var/url_coverage.txt
            rb"^INFO: URL coverage report is in",
            # Example: -- Running tests in parallel mode with 4 processes
            rb"^-- Running tests in",
            rb"^OK",
            # Example: Ran 2139 tests in 115.659s
            rb"^Ran [0-9]+ tests in",
            # Destroying test database for alias 'default'...
            rb"^Destroying test database for alias ",
            rb"^Using existing clone",
            rb"^\*\* Skipping ",
        ]
        self.compiled_line_pattern = re.compile(rb"|".join(valid_line_patterns))
        self.partial_line = b""
        self.full_extra_output = bytearray()

    def find_extra_output(self, data: bytes) -> None:
        *lines, self.partial_line = (self.partial_line + data).split(b"\n")
        for line in lines:
            if not self.compiled_line_pattern.match(line):
                self.full_extra_output += line + b"\n"


class WrappedIO(IO[bytes]):
    def __init__(self, stream: IO[bytes], extra_output_finder: ExtraConsoleOutputFinder) -> None:
        self.stream = stream
        self.extra_output_finder = extra_output_finder

    @property
    @override
    def mode(self) -> str:
        return self.stream.mode

    @property
    @override
    def name(self) -> str:
        return self.stream.name

    @override
    def close(self) -> None:
        pass

    @property
    @override
    def closed(self) -> bool:
        return self.stream.closed

    @override
    def fileno(self) -> int:
        return self.stream.fileno()

    @override
    def flush(self) -> None:
        self.stream.flush()

    @override
    def isatty(self) -> bool:
        return self.stream.isatty()

    @override
    def read(self, n: int = -1) -> bytes:
        return self.stream.read(n)

    @override
    def readable(self) -> bool:
        return self.stream.readable()

    @override
    def readline(self, limit: int = -1) -> bytes:
        return self.stream.readline(limit)

    @override
    def readlines(self, hint: int = -1) -> List[bytes]:
        return self.stream.readlines(hint)

    @override
    def seek(self, offset: int, whence: int = SEEK_SET) -> int:
        return self.stream.seek(offset, whence)

    @override
    def seekable(self) -> bool:
        return self.stream.seekable()

    @override
    def tell(self) -> int:
        return self.stream.tell()

    @override
    def truncate(self, size: Optional[int] = None) -> int:
        return self.truncate(size)

    @override
    def writable(self) -> bool:
        return self.stream.writable()

    @override
    def write(self, data: "ReadableBuffer") -> int:
        num_chars = self.stream.write(data)
        self.extra_output_finder.find_extra_output(bytes(data))
        return num_chars

    @override
    def writelines(self, data: "Iterable[ReadableBuffer]") -> None:
        data, data_copy = itertools.tee(data)
        self.stream.writelines(data)
        lines = b"".join(data_copy)
        self.extra_output_finder.find_extra_output(lines)

    @override
    def __next__(self) -> bytes:
        return next(self.stream)

    @override
    def __iter__(self) -> Iterator[bytes]:
        return self

    @override
    def __enter__(self) -> IO[bytes]:
        self.stream.__enter__()
        return self

    @override
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.stream.__exit__(exc_type, exc_value, traceback)


@contextmanager
def tee_stderr_and_find_extra_console_output(
    extra_output_finder: ExtraConsoleOutputFinder,
) -> Iterator[None]:
    stderr = sys.stderr

    # get shared console handler instance from any logger that have it
    console_log_handler = logging.getLogger("django.server").handlers[0]
    assert isinstance(console_log_handler, logging.StreamHandler)
    assert console_log_handler.stream == stderr

    sys.stderr = console_log_handler.stream = TextIOWrapper(
        WrappedIO(stderr.buffer, extra_output_finder), line_buffering=True
    )
    try:
        yield
    finally:
        try:
            sys.stderr.flush()
        finally:
            sys.stderr = console_log_handler.stream = stderr


@contextmanager
def tee_stdout_and_find_extra_console_output(
    extra_output_finder: ExtraConsoleOutputFinder,
) -> Iterator[None]:
    stdout = sys.stdout
    sys.stdout = TextIOWrapper(
        WrappedIO(sys.stdout.buffer, extra_output_finder), line_buffering=True
    )
    try:
        yield
    finally:
        try:
            sys.stdout.flush()
        finally:
            sys.stdout = stdout
