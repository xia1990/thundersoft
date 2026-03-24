import os
import subprocess
from xml.etree import ElementTree as ET
from datetime import datetime
import shutil
import argparse
import sys
import json

def run_command(cmd, cwd=None):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {cmd}")
        print(f"[STDERR] {e.stderr}")
        raise


def get_latest_commit_hash(repo_url, branch):
    """Return the latest commit hash for a given repo and branch."""
    output = run_command(f"git ls-remote {repo_url} refs/heads/{branch}")
    return output.split()[0]


def update_manifest_revisions(manifest_path, branch, output_file, parent_fetch=None, snapshot_dir="snapshots"):
    """
    Update revisions in manifest and its includes, and save snapshots.
    所有 snapshot 文件统一放到 snapshot_dir 下，命名规则:
      xxx.xml -> xxx_snapshot.xml
    """
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # 解析 fetch（如果没有，则继承父的）
    remote = root.find("remote")
    fetch = remote.get("fetch") if (remote is not None and remote.get("fetch")) else parent_fetch

    # 更新 project revisions
    for project in root.findall("project"):
        repo_name = project.get("name")
        if not repo_name:
            continue

        if repo_name == "apricot-android-mb/tools/app_tool":
            repo_url = "https://git.sb.com/apricot-android-mb/tools/app_tool.git"
            print(f"[INFO] Processing {repo_name} -> {repo_url}")
            latest_hash = get_latest_commit_hash(repo_url, branch)
            project.set("revision", latest_hash)
            project.set("upstream", f"refs/heads/{branch}")
        else:
            repo_url = f"{fetch}/{repo_name}" if fetch else repo_name
            print(f"[INFO] Processing {repo_name} -> {repo_url}")
            ref = project.get("revision") or branch
            latest_hash = get_latest_commit_hash(repo_url, ref)
            project.set("revision", latest_hash)
            if not project.get("upstream"):
                project.set("upstream", f"refs/heads/{branch}")

    # 递归 include -> snapshots/xxx_snapshot.xml
    manifest_dir = os.path.dirname(manifest_path) or "."
    os.makedirs(snapshot_dir, exist_ok=True)

    for include in root.findall("include"):
        include_name = include.get("name")
        if not include_name:
            continue

        include_path = include_name if os.path.isabs(include_name) else os.path.normpath(os.path.join(manifest_dir, include_name))
        print("="*100)
        print(include_path)
        print("="*100)
        if not os.path.isfile(include_path):
            print(f"\033[1;33m[WARN] include file not found, skipping: {include_path}\033[0m")
            continue

        # 用 basename 转成 snapshot 名字: xxx.xml -> xxx_snapshot.xml
        base_name, _ = os.path.splitext(os.path.basename(include_name))
        child_snapshot_file = f"{base_name}_snapshot.xml"
        child_snapshot_path = os.path.join(snapshot_dir, child_snapshot_file)

        # 递归生成子 snapshot
        child_saved = update_manifest_revisions(
            include_path, branch, child_snapshot_path, parent_fetch=fetch, snapshot_dir=snapshot_dir
        )

        # include 指向 snapshot_dir 下的文件
        rel_to_parent = os.path.relpath(child_saved, start=os.path.dirname(output_file) or ".")
        include.set("name", rel_to_parent)
        print(f"[INFO] include '{include_name}' -> '{child_saved}'")

    # 保存当前 manifest snapshot
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"\033[1;32m[INFO] Snapshot saved: {output_file}\033[0m")

    return output_file


def prepare_and_update_repo(name, manifest_url, manifest_file, branch, repo_url, repo_rev, root_dir):
    """Create directory, initialize repo, and update manifest."""
    print(f"[INFO] Initializing {name} repo...")
    repo_dir = os.path.join(root_dir, "repos", name)
    os.makedirs(repo_dir, exist_ok=True)

    os.chdir(repo_dir)
    init_cmd = f"repo init --depth=1 -u {manifest_url} -m {manifest_file} -b {branch} --repo-url={repo_url} --repo-rev={repo_rev} --no-clone-bundle -g all"
    run_command(init_cmd)

    manifest_path = os.path.join(repo_dir, ".repo", "manifests", manifest_file)
    new_manifest_name = f"{name}_snapshot.xml"
    print("manifest_path:", manifest_path , "new_manifest_name:", new_manifest_name)
    # sys.exit()
    # new_manifest_name = f"{name}_manifest.xml"
    update_manifest_revisions(manifest_path, branch, output_file = new_manifest_name)

    os.chdir(root_dir)


def main():
    parser = argparse.ArgumentParser(description="Update and snapshot manifests with latest commit hashes.")
    args = parser.parse_args()

    root_dir = os.getcwd()
    repos_dir = os.path.join(root_dir, "repos")

    # Clean old repos
    if os.path.exists(repos_dir):
        shutil.rmtree(repos_dir)
    os.makedirs(repos_dir)

    android_manifest = "https://git.sb.com/apricot-android-mb/manifest.git"
    qnx_manifest = "https://git.sb.com/sb/apricotqal/apricotqal-qnx-manifests.git"
    nonhlos_manifest = "https://git.sb.com/apricot-nonhlos-mb/apricotqal/nonhlos-manifests.git"
    repo_url = "https://git.sb.com/apricot/git-repo-mirror.git"
    branch = "i2_max_8295_master"
    repo_rev = "v2.31"


    # Prepare all repos
    prepare_and_update_repo("dolphin", android_manifest, "dolphin_manifest.xml", branch, repo_url, repo_rev, root_dir)
    prepare_and_update_repo("durian", android_manifest, "durian_manifest.xml", branch, repo_url, repo_rev, root_dir)
    prepare_and_update_repo("qnx", qnx_manifest, "default.xml", branch, repo_url, repo_rev, root_dir)
    prepare_and_update_repo("nonhlos", nonhlos_manifest, "default.xml", branch, repo_url, repo_rev, root_dir)

    print("[SUCCESS] All manifests updated successfully.")

if __name__ == "__main__":
    print("\033[31m 此脚本会生成各自的快照文件，include不会合并 \033[0m")
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Unhandled exception: {e}")
        sys.exit(1)
