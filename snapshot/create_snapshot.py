import os
import subprocess
from xml.etree import ElementTree as ET
from datetime import datetime
import shutil
import argparse
import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed


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

# def get_latest_commit_hash(repo_url, branch):
#     """Return tag hash if exists, otherwise branch hash."""

#     tag_ref = "refs/heads/E247.0-6.6-895743-alpha"

#     # 1. try tag first
#     tag_output = run_command(f"git ls-remote {repo_url} {tag_ref}").strip()
#     if tag_output:
#         print("\033[1;32m 根据TAG来获取hash值 \033[0m") 
#         return tag_output.split()[0]

#     # 2. fallback to branch
#     branch_ref = f"refs/heads/{branch}"
#     branch_output = run_command(f"git ls-remote {repo_url} {branch_ref}").strip()
#     if branch_output:
#         return branch_output.split()[0]

#     raise RuntimeError(f"Cannot find tag or branch: {tag_ref}, {branch_ref}")


def get_latest_commit_hash_safe(repo_url, branch):
    """Wrapper to safely get commit hash (returns None on failure)."""
    try:
        return get_latest_commit_hash(repo_url, branch)
    except Exception as e:
        print(f"[WARN] Failed to get hash for {repo_url} ({branch}): {e}")
        return None


def update_manifest_revisions(manifest_path, branch):
    """Update revisions in the manifest and save a snapshot (parallelized)."""
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # 根据 manifest 文件路径设置默认 fetch（统一平台）
    if "qnx" in manifest_path.lower():
        parent_fetch = "https://git.sb.com"
    else:
        parent_fetch = "https://git.sb.com/sb/android/AOSP"

    # 构建 remote fetch map
    fetch_map = {}
    for remote in root.findall('remote'):
        name = remote.get("name")
        fetch_url = remote.get("fetch")
        if name and fetch_url:
            fetch_map[name] = fetch_url

    # 收集所有 project
    projects = []
    for project in root.findall('project'):
        repo_name = project.get('name')
        if not repo_name:
            continue

        remote_name = project.get('remote')
        # 优先用 remote 的 fetch，如果没有则继承 parent_fetch
        fetch = fetch_map.get(remote_name) if remote_name else None
        if not fetch:
            fetch = parent_fetch

        projects.append((project, repo_name, fetch))
        print(f"[DEBUG] Project: {repo_name}, Remote: {remote_name}, Fetch: {fetch}")

    print(f"[INFO] Processing {len(projects)} projects in parallel...")

    # 并行更新 commit hash
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for project, repo_name, fetch in projects:
            repo_url = f"{fetch}/{repo_name}"

            # 特殊 QSSI case
            if repo_name == "vendor/qcom/proprietary" and "qssi" in manifest_path.lower():
                special_ref = "8295_master_qssi"
                futures[executor.submit(get_latest_commit_hash_safe, repo_url, special_ref)] = (
                    project, repo_name, repo_url, special_ref, True)
            else:
                # ref = project.get('revision') or branch
                ref = branch
                futures[executor.submit(get_latest_commit_hash_safe, repo_url, ref)] = (
                    project, repo_name, repo_url, ref, False)

        for future in as_completed(futures):
            project, repo_name, repo_url, ref, special = futures[future]
            latest_hash = future.result()
            if latest_hash:
                if special:
                    project.set('revision', latest_hash)
                    project.set('upstream', f"refs/heads/{ref}")
                else:
                    project.set('revision', latest_hash)
                    if not project.get('upstream'):
                        project.set('upstream', f"refs/heads/{branch}")
                print(f"[INFO] Updated {repo_name} ({ref}) -> {latest_hash}")
            else:
                print(f"[WARN] Skipped {repo_name} due to missing hash")

    # 保存快照
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_manifest_name = f"{os.path.splitext(manifest_path)[0]}_snapshot_{timestamp}.xml"
    tree.write(new_manifest_name)
    print(f"[INFO] Snapshot saved: {new_manifest_name}")
    return new_manifest_name


def prepare_and_update_repo(name, manifest_url, manifest_file, branch, repo_url, repo_rev, root_dir):
    """Create directory, initialize repo, and update manifest."""
    print(f"[INFO] Initializing {name} repo...")
    repo_dir = os.path.join(root_dir, "repos", name)
    os.makedirs(repo_dir, exist_ok=True)

    os.chdir(repo_dir)
    init_cmd = f"repo init --depth=1 -u {manifest_url} -m {manifest_file} -b {branch} --repo-url={repo_url} --repo-rev={repo_rev} --no-clone-bundle -g all"
    run_command(init_cmd)

    manifest_path = os.path.join(repo_dir, ".repo", "manifests", manifest_file)
    snapshot = update_manifest_revisions(manifest_path, branch)
    new_snapshot = f'{name}_manifest.xml'
    os.rename(snapshot, new_snapshot)
    os.chdir(root_dir)

def get_amss_log(amss_repo, branch, root_dir, save_file="amss_manifest.xml"):
    """
    Clone repo, get latest commit id of branch, and write to txt file.
    """
    repo_dir = os.path.join(root_dir, "repos", "amss")
    os.makedirs(repo_dir, exist_ok=True)

    os.chdir(repo_dir)
    repo_name = amss_repo.split("/")[-1].replace(".git", "")

    # clone
    run_command(f"git clone -b {branch} {amss_repo} --depth=1")

    # get commit id
    commit_id = run_command("git log -1 --pretty=format:%H", cwd=repo_name)

    # write to txt
    with open(save_file, "w", encoding="utf-8") as f:
        f.write(commit_id)

    return commit_id

def main():
    parser = argparse.ArgumentParser(description="Update and snapshot manifests with latest commit hashes.")
    args = parser.parse_args()

    root_dir = os.getcwd()
    repos_dir = os.path.join(root_dir, "repos")

    # Clean old repos
    if os.path.exists(repos_dir):
        shutil.rmtree(repos_dir)
    os.makedirs(repos_dir)

    aosp_manifest = "https://git.sb.com/sb/android/aosp-manifest.git"
    qnx_manifest = "https://git.sb.com/sb/qnx/qnx-manifest.git"
    amss_repo = "https://git.sb.com/sb/sa8295p-hqx-4-5-5-1_amss_standard_oem.git"
    repo_url = "https://git.sb.com/apricot/git-repo-mirror.git"
    branch = "8295_master"
    repo_rev = "v2.31"

    # Prepare all repos
    prepare_and_update_repo("vendor", aosp_manifest, "8295_master_vendor.xml", branch, repo_url, repo_rev, root_dir)
    prepare_and_update_repo("qssi", aosp_manifest, "8295_master_qssi.xml", branch, repo_url, repo_rev, root_dir)
    prepare_and_update_repo("qnx", qnx_manifest, "8295_master.xml", branch, repo_url, repo_rev, root_dir)
    get_amss_log(amss_repo, branch, root_dir, save_file="amss_manifest.xml")

    print("[SUCCESS] All manifests updated successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Unhandled exception: {e}")
        sys.exit(1)
