import os
import subprocess
from xml.etree import ElementTree as ET
import shutil
import argparse
import sys
import copy


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


def merge_manifest_revisions(manifest_path, branch, parent_fetch=None):
    """
    递归更新 revisions，并把子 include 内联合并到父 manifest。
    返回 project 元素列表。
    """
    tree = ET.parse(manifest_path)
    root = tree.getroot()

    # 当前 manifest 的 fetch（如果没有，则继承父的）
    remote = root.find("remote")
    if remote is not None and remote.get("fetch"):
        fetch = remote.get("fetch")
    else:
        fetch = parent_fetch

    new_projects = []

    # 解析 manifest 里的 project
    for project in root.findall("project"):
        repo_name = project.get("name")
        if not repo_name:
            continue

        if repo_name == "sb/tools/app_tool":
            repo_url = "https://git.sb.com/sb/tools/app_tool.git"
            print(f"[INFO] Processing {repo_name} -> {repo_url}")
            latest_hash = get_latest_commit_hash(repo_url, branch)
            print(f"[INFO] revision -> {branch}, hash -> {latest_hash}")
            project.set("revision", latest_hash)
            project.set("upstream", f"refs/heads/{branch}")
        else:
            repo_url = f"{fetch}/{repo_name}"
            print(f"[INFO] Processing {repo_name} -> {repo_url}")
            ref = project.get("revision") or branch
            latest_hash = get_latest_commit_hash(repo_url, ref)
            print(f"[INFO] Latest hash for {repo_name}: {latest_hash}")
            project.set("revision", latest_hash)
            if not project.get("upstream"):
                project.set("upstream", f"refs/heads/{branch}")

        new_projects.append(project)

    # 递归处理 include -> inline 合并
    for include in root.findall("include"):
        include_file = include.get("name")
        if include_file:
            include_path = os.path.join(os.path.dirname(manifest_path), include_file)
            child_projects = merge_manifest_revisions(include_path, branch, parent_fetch=fetch)
            new_projects.extend(child_projects)
            root.remove(include)  # 移除 include 标签
        else:
            continue

    return new_projects


def generate_final_snapshot(root_manifest, branch, output_file):
    """生成最终合并后的快照文件（含正确换行/缩进）"""
    projects = merge_manifest_revisions(root_manifest, branch)

    # 构建新 manifest 根节点
    new_root = ET.Element("manifest")

    # 从 root_manifest 拷贝 remote/default（deepcopy 避免移动原节点）
    src_tree = ET.parse(root_manifest)
    src_root = src_tree.getroot()
    for tag in ("remote", "default"):
        for elem in src_root.findall(tag):
            new_root.append(copy.deepcopy(elem))

    # 追加所有项目（也 deepcopy，统一风格）
    for proj in projects:
        new_root.append(copy.deepcopy(proj))

    out_tree = ET.ElementTree(new_root)

    # 统一缩进/换行：优先使用 Python 3.9+ 的 ET.indent
    try:
        ET.indent(out_tree, space="  ", level=0)  # Python 3.9+
    except AttributeError:
        # 兼容旧版本 Python 的缩进实现
        def _indent(elem, level=0):
            i = "\n" + level * "  "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                for child in elem:
                    _indent(child, level + 1)
                    if not child.tail or not child.tail.strip():
                        child.tail = i + "  "
                if not elem[-1].tail or not elem[-1].tail.strip():
                    elem[-1].tail = i
            else:
                if not elem.text or not elem.text.strip():
                    elem.text = ""
        _indent(new_root)

    out_tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"\033[1;32m [INFO] Final merged snapshot saved: {output_file} \033[0m")

    
def generate_final_snapshot_source(root_manifest, branch, output_file):
    """生成最终合并后的快照文件"""
    projects = merge_manifest_revisions(root_manifest, branch)

    # 构建新 manifest 根节点
    new_root = ET.Element("manifest")

    # 插入 remote/default（从 root_manifest 拷贝）
    tree = ET.parse(root_manifest)
    root = tree.getroot()
    for tag in ["remote", "default"]:
        for elem in root.findall(tag):
            new_root.append(elem)

    # 插入所有项目
    for proj in projects:
        new_root.append(proj)

    tree = ET.ElementTree(new_root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"\033[1;32m [INFO] Final merged snapshot saved: {output_file} \033[0m")


def prepare_and_update_repo(name, manifest_url, manifest_file, branch, repo_url, repo_rev, root_dir):
    """Create directory, initialize repo, and generate merged snapshot."""
    print(f"[INFO] Initializing {name} repo...")
    repo_dir = os.path.join(root_dir, "repos", name)
    os.makedirs(repo_dir, exist_ok=True)

    os.chdir(repo_dir)
    init_cmd = f"repo init --depth=1 -u {manifest_url} -m {manifest_file} -b {branch} " \
               f"--repo-url={repo_url} --repo-rev={repo_rev} --no-clone-bundle -g all"
    run_command(init_cmd)

    manifest_path = os.path.join(repo_dir, ".repo", "manifests", manifest_file)

    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # output_snapshot = os.path.join(repo_dir, f"{name}_snapshot.xml")
    output_snapshot = os.path.join(repo_dir, f"{name}_manifest.xml")
    generate_final_snapshot(manifest_path, branch, output_file=output_snapshot)

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

    android_manifest = "https://git.sb.com/sb/manifest.git"
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

    print("[SUCCESS] All manifests updated and merged successfully.")


if __name__ == "__main__":
    print("\033[31m 此脚本会生成一个合并总的快照文件，include会合并 \033[0m")
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Unhandled exception: {e}")
        sys.exit(1)
