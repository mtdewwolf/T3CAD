import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile

from .core import CadError, Document, Harness


def read_json(path: str):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CadError("invalid_input", f"Duplicate JSON field: {key!r}.")
            result[key] = value
        return result

    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text, object_pairs_hook=unique_object)


@contextlib.contextmanager
def document_lock(path: Path):
    try:
        import fcntl
    except ImportError:
        raise CadError("unsupported_platform", "The prototype file store currently requires POSIX file locking.") from None
    with path.with_name(path.name + ".lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def save_document(path: Path, document: Document) -> None:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(document.to_dict(), temporary, indent=2, allow_nan=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="T3CAD headless document and agent harness prototype")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="Describe the current harness")
    create = commands.add_parser("create", help="Create an empty millimeter document")
    create.add_argument("document")
    create.add_argument("--id", required=True)
    inspect = commands.add_parser("inspect", help="Inspect features and analytic preview measurements")
    inspect.add_argument("document")
    apply = commands.add_parser("apply", help="Apply an atomic JSON request; use - for stdin")
    apply.add_argument("document")
    apply.add_argument("request")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    harness = Harness()
    try:
        if arguments.command == "capabilities":
            result = harness.capabilities()
        else:
            path = Path(arguments.document).resolve()
            request = read_json(arguments.request) if arguments.command == "apply" else None
            with document_lock(path):
                if arguments.command == "create":
                    if path.exists():
                        raise CadError("document_exists", "Refusing to overwrite an existing document.")
                    document = Document(arguments.id)
                    save_document(path, document)
                    result = harness.inspect(document)
                else:
                    document = Document.from_dict(read_json(str(path)))
                    if arguments.command == "inspect":
                        result = harness.inspect(document)
                    else:
                        candidate, result = harness.apply(document, request)
                        if not result["replayed"]:
                            save_document(path, candidate)
        print(json.dumps({"ok": True, "result": result}, indent=2, allow_nan=False))
        return 0
    except (CadError, OSError, ValueError, RecursionError) as error:
        code = error.code if isinstance(error, CadError) else "io_error" if isinstance(error, OSError) else "invalid_input"
        print(json.dumps({"ok": False, "error": {"code": code, "message": str(error)}}), file=sys.stderr)
        return 1
