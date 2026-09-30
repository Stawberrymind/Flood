"""Crash-safe replacement of workspace products and checkpoints."""

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile


@contextmanager
def atomic_path(path):
    """Yield a same-directory temporary path; replace the target only on success."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.stem}-", suffix=target.suffix,
                                dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path, text):
    with atomic_path(path) as temporary:
        temporary.write_text(text, encoding="utf-8")
