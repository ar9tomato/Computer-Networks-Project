"""
make_zip.py

Packages the entire project (source code, generated CSV metrics, graphs,
and visualization scripts) into a single deliverable archive:

    Member1_AODV_EAURP_Review2.zip

Usage (from the project root, after run_experiments.py and visualize.py
have already been executed at least once):
    python make_zip.py
"""

import os
import zipfile

ZIP_NAME = "Member1_AODV_EAURP_Review2.zip"

# Files and directories included in the deliverable archive. Directories
# are walked recursively; individual files are added directly.
INCLUDE_PATHS = [
    "core",
    "protocols",
    "results",
    "graphs",
    "run_experiments.py",
    "visualize.py",
    "make_zip.py",
    "README.md",
    "requirements.txt",
]

# Never package caches, bytecode, or the archive itself.
EXCLUDE_DIR_NAMES = {"__pycache__", ".git", ".ipynb_checkpoints"}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo")


def should_skip_dir(dirname):
    return dirname in EXCLUDE_DIR_NAMES


def should_skip_file(filename):
    return filename.endswith(EXCLUDE_FILE_SUFFIXES) or filename == ZIP_NAME


def add_path_to_zip(zf, path):
    if os.path.isfile(path):
        if not should_skip_file(os.path.basename(path)):
            zf.write(path, arcname=path)
        return

    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            for filename in files:
                if should_skip_file(filename):
                    continue
                full_path = os.path.join(root, filename)
                zf.write(full_path, arcname=full_path)


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    included = [p for p in INCLUDE_PATHS if os.path.exists(p)]
    missing = [p for p in INCLUDE_PATHS if not os.path.exists(p)]

    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in included:
            add_path_to_zip(zf, path)

    print(f"Created {ZIP_NAME} with:")
    for path in included:
        print(f"  + {path}")
    if missing:
        print("\nSkipped (not found):")
        for path in missing:
            print(f"  - {path}")

    print(f"\nDone. Archive size: {os.path.getsize(ZIP_NAME) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
