import argparse
import getpass
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a Hugging Face Space.")
    parser.add_argument("--space-id", required=True, help="Space id, for example username/universal-translator")
    parser.add_argument("--folder", default="hf-space", help="Folder to upload to the Space repo")
    parser.add_argument("--private", action="store_true", help="Create the Space as private")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")

    token = os.getenv("HF_TOKEN") or getpass.getpass("Hugging Face write token: ")
    if not token:
        raise SystemExit("A Hugging Face write token is required.")

    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit("Install huggingface_hub first: python -m pip install huggingface_hub") from exc

    api = HfApi(token=token)
    user = api.whoami(token=token).get("name", "unknown")
    print(f"Authenticated as {user}")

    api.create_repo(
        repo_id=args.space_id,
        repo_type="space",
        space_sdk="gradio",
        private=args.private,
        exist_ok=True,
        token=token,
    )
    api.upload_folder(
        folder_path=str(folder),
        repo_id=args.space_id,
        repo_type="space",
        commit_message="Deploy Universal Translator Space",
        token=token,
    )

    print(f"Space deployed: https://huggingface.co/spaces/{args.space_id}")


if __name__ == "__main__":
    main()
