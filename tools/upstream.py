import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent


def git(checkout: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def verify(checkout: Path, lock: dict) -> dict:
    repository_root = Path(git(checkout, "rev-parse", "--show-toplevel")).resolve()
    if repository_root != checkout.resolve():
        raise ValueError("The checkout path must be its own repository, not a directory in another repository.")
    if git(checkout, "remote", "get-url", "origin") != lock["repository"]:
        raise ValueError("Checkout origin does not match the source lock.")
    if git(checkout, "rev-parse", "HEAD") != lock["commit"]:
        raise ValueError("Checkout revision does not match the source lock; no reset was performed.")
    if git(checkout, "rev-parse", f"refs/tags/{lock['tag']}^{{commit}}") != lock["commit"]:
        raise ValueError("The local release tag does not resolve to the pinned commit.")
    if git(checkout, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Reference checkout has local changes; no files were changed or removed.")
    digest = hashlib.sha256((checkout / "LICENSE").read_bytes()).hexdigest()
    if digest != lock["root_license_sha256"]:
        raise ValueError("The root license fingerprint does not match the source lock.")
    return {
        "ok": True,
        "checkout": str(checkout),
        "repository": lock["repository"],
        "tag": lock["tag"],
        "commit": lock["commit"],
        "root_license": lock["root_license"],
        "integration_status": lock["integration_status"],
        "verified": ["repository_root", "origin", "commit", "tag", "clean_worktree", "root_license_fingerprint"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch or verify the pinned T3 Code reference source.")
    parser.add_argument("--fetch", action="store_true", help="Clone the pinned tag only if the checkout is absent.")
    parser.add_argument("--setup-app", action="store_true", help="Set up .work/app and apply T3CAD patches.")
    arguments = parser.parse_args()
    try:
        lock = json.loads((ROOT / "upstream/t3code.lock.json").read_text(encoding="utf-8"))
        checkout = (ROOT / lock["checkout"]).resolve()
        if not checkout.is_relative_to(ROOT / ".work/upstream"):
            raise ValueError("The reference checkout must remain under .work/upstream.")
        if not checkout.exists():
            if not arguments.fetch and not arguments.setup_app:
                raise ValueError("Reference source is absent. Run python3 tools/upstream.py --fetch.")
            checkout.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", lock["tag"], "--", lock["repository"], str(checkout)],
                check=True, stdout=sys.stderr,
            )
        if arguments.setup_app:
            app_dir = (ROOT / ".work/app").resolve()
            if not app_dir.exists():
                app_dir.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", lock["tag"], str(checkout), str(app_dir)],
                    check=True,
                )
                patches = sorted((ROOT / "patches").glob("*.patch"))
                for patch in patches:
                    subprocess.run(
                        ["git", "-C", str(app_dir), "am", str(patch)],
                        check=True,
                    )
            print(json.dumps({"ok": True, "app": str(app_dir), "ready": True}, indent=2))
            return 0
        print(json.dumps(verify(checkout, lock), indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        message = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(json.dumps({"ok": False, "error": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
