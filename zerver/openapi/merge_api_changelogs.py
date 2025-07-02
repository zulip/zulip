import glob
import os
import re
from pathlib import Path


def get_changelog_files_list() -> list[str]:
    dir_path = Path("api_docs/unmerged.d")
    if os.path.exists(dir_path):
        return [os.path.basename(path) for path in glob.glob(f"{dir_path}/ZF-??????.md")]

    return []


def get_unmerged_changelogs(verbose: bool = True) -> str:
    changelogs = ""
    dir_path = Path("api_docs/unmerged.d")
    changelog_files_list = get_changelog_files_list()
    if verbose:
        if changelog_files_list:
            print(f"Unmerged changelog files: {changelog_files_list}")
        else:
            print("No unmerged changelog files found.")

    for file_name in changelog_files_list:
        file_path = Path(f"{dir_path}/{file_name}")
        with open(file_path) as f:
            changelogs += f.read().strip("\n") + "\n"

    return changelogs


def get_feature_level(update_feature_level: bool = True) -> int:
    new_feature_level = None
    version_file_path = Path("version.py")

    with open(version_file_path) as file:
        lines = file.readlines()

    new_feature_level = None

    with open(version_file_path, "w") as file:
        for line in lines:
            if line.startswith("API_FEATURE_LEVEL = "):
                match = re.search(r"\d+", line)
                if match:
                    new_feature_level = int(match.group()) + 1
                    if update_feature_level:
                        file.write(f"API_FEATURE_LEVEL = {new_feature_level}\n")
                        continue

            file.write(line)

    assert new_feature_level is not None
    if update_feature_level:
        print(f"Updated API feature level: {new_feature_level - 1} -> {new_feature_level}")
    return new_feature_level


def get_current_major_version() -> str | None:
    changelog_path = Path("api_docs/changelog.md")
    with open(changelog_path) as file:
        for line in file:
            match = re.search(r"## Changes in Zulip (\d+\.\d+)", line)
            if match:
                return match.group(1)
    return None


def merge_changelogs(changelogs: str, new_feature_level: int, update_changelog: bool = True) -> str:
    changelogs_merged = False
    changelog_path = Path("api_docs/changelog.md")

    changelog_markdown_string = ""

    with open(changelog_path) as file:
        lines = file.readlines()

    changelogs_merged = False

    with open(changelog_path, "w") as file:
        for line in lines:
            file.write(line)
            changelog_markdown_string += line
            if changelogs_merged:
                continue
            if re.fullmatch(r"## Changes in Zulip \d+\.\d+\n", line):
                changelogs_merged = True
                updates = f"\n**Feature level {new_feature_level}**\n\n{changelogs}"
                changelog_markdown_string += updates
                if update_changelog:
                    file.write(updates)

    if update_changelog:
        print(f"Changelogs merged to {changelog_path}.")
    return changelog_markdown_string


def update_feature_level_in_api_docs(new_feature_level: int) -> None:
    changelog_files_list = get_changelog_files_list()
    num_replaces = 0
    current_version = get_current_major_version()

    # Get all the markdown files in api_docs folder along with zulip.yaml.
    api_docs_folder = Path("api_docs")
    api_docs_paths = list(api_docs_folder.glob("*.md"))
    api_docs_paths.append(Path("zerver/openapi/zulip.yaml"))

    for api_docs_path in api_docs_paths:
        with open(api_docs_path) as file:
            lines = file.readlines()

        num_replaces = 0

        with open(api_docs_path, "w") as file:
            for line in lines:
                old_line = line
                for file_name in changelog_files_list:
                    temporary_feature_level = file_name[: -len(".md")]

                    pattern = rf"Zulip \d+\.\d+ \(feature level {temporary_feature_level}\)"
                    replacement = f"Zulip {current_version} (feature level {new_feature_level})"
                    line = re.sub(pattern, replacement, line)

                if old_line != line:
                    num_replaces += 1

                file.write(line)

        if num_replaces:
            print(f"Updated {api_docs_path}; {num_replaces} replaces were made.")


def remove_unmerged_changelog_files() -> None:
    changelog_files_list = get_changelog_files_list()
    for file_name in changelog_files_list:
        os.remove(Path(f"api_docs/unmerged.d/{file_name}"))

    if changelog_files_list:
        print("Removed all the unmerged changelog files.")
