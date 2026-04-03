import xml.etree.ElementTree as ET
import requests
import os
import urllib.parse
import sys
from configparser import ConfigParser
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


def shell(command, result=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()
    return_code = process.wait()

    if result and return_code != 0:
        print(command, ': 命令执行失败', return_code, stderr.decode())

    return return_code, stdout.decode()


def download_manifest(artifactory_url, token, source_file, target_file):
    down_command = (
        f'jf rt dl "{source_file}" "{target_file}" '
        f'--url={artifactory_url} --user=GAYUXIA --password={token} --flat=true'
    )
    print(down_command)
    shell(down_command, result=True)

# 创建分支
def create_one_branch(session, headers, GITLAB_URL, base_repo_path, manifest_path, project, new_branch):
    name = project.get("name")
    revision = project.get("revision")

    if not name or not revision:
        return None

    if name == "vendor/qcom/proprietary" and os.path.basename(manifest_path) == "qssi_manifest.xml":
        ref_branch = f"{new_branch}_qssi"
    else:
        ref_branch = new_branch

    if manifest_path == "qnx_manifest.xml":
        full_project_path = name
    else:
        full_project_path = os.path.join(base_repo_path, name)

    project_path_encoded = urllib.parse.quote(full_project_path, safe='')
    url = f"{GITLAB_URL}/api/v4/projects/{project_path_encoded}/repository/branches"

    params = {
        "branch": ref_branch,
        "ref": revision
    }

    try:
        r = session.post(url, headers=headers, params=params, timeout=10)

        if r.status_code == 201:
            return f"[OK] {name}"
        elif r.status_code == 400 and "already exists" in r.text:
            return f"[SKIP] {name} {new_branch} already exists"
        else:
            return f"[FAIL] {name} {r.status_code} {r.text[:100]}"
    except Exception as e:
        return f"[ERR] {name} {e}"

def create_branches_from_manifest(manifest_path, GITLAB_TOKEN, GITLAB_URL, base_repo_path, new_branch, workers=16):
    print(f"\n===== 开始处理 {manifest_path} =====")

    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    projects = root.findall("project")

    print(f"发现 {len(projects)} 个仓库")

    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []

            for project in projects:
                futures.append(
                    executor.submit(
                        create_one_branch,
                        session,
                        headers,
                        GITLAB_URL,
                        base_repo_path,
                        manifest_path,
                        project,
                        new_branch
                    )
                )

            for f in as_completed(futures):
                result = f.result()
                if result:
                    print(result)


# 删除分支                  
def delete_one_branch(session, headers, GITLAB_URL, base_repo_path, manifest_path, project, del_branch):
    name = project.get("name")

    if not name:
        return None

    if manifest_path == "qnx_manifest.xml":
        full_project_path = name
    else:
        full_project_path = os.path.join(base_repo_path, name)

    project_path_encoded = urllib.parse.quote(full_project_path, safe='')
    branch_encoded = urllib.parse.quote(del_branch, safe='')
    url = f"{GITLAB_URL}/api/v4/projects/{project_path_encoded}/repository/branches/{branch_encoded}"

    try:
        r = session.delete(url, headers=headers, timeout=10)

        if r.status_code == 204:
            return f"[DEL OK] {name}"
        elif r.status_code == 404:
            return f"[SKIP] {name} 分支不存在"
        else:
            return f"[FAIL] {name} {r.status_code} {r.text[:100]}"
    except Exception as e:
        return f"[ERR] {name} {e}"

def delete_branches_from_manifest(manifest_path, GITLAB_TOKEN, GITLAB_URL, base_repo_path, del_branch, workers=16):
    print(f"\n===== 开始删除 {manifest_path} 分支 {del_branch} =====")

    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    tree = ET.parse(manifest_path)
    root = tree.getroot()
    projects = root.findall("project")

    print(f"发现 {len(projects)} 个仓库")

    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []

            for project in projects:
                futures.append(
                    executor.submit(
                        delete_one_branch,
                        session,
                        headers,
                        GITLAB_URL,
                        base_repo_path,
                        manifest_path,
                        project,
                        del_branch
                    )
                )

            for f in as_completed(futures):
                result = f.result()
                if result:
                    print(result)


if __name__ == "__main__":
    config = ConfigParser()
    config.read("/home/gayuxia/config.ini")

    GITLAB_TOKEN = config.get("gitlab", "token")
    GITLAB_URL = config.get("gitlab", "url")
    artifactory_url = config.get("artifact", "url")
    artifactory_token = config.get("artifact", "token")

    parser = argparse.ArgumentParser()
    parser.add_argument('--new_branch', default='8295_master')
    parser.add_argument('--vendor_source_file')
    parser.add_argument('--qssi_source_file')
    parser.add_argument('--qnx_source_file')

    args = parser.parse_args()

    new_branch = args.new_branch
    vendor_source_file = args.vendor_source_file
    qssi_source_file = args.qssi_source_file
    qnx_source_file = args.qnx_source_file

    base_repo_path = "RSE/android/AOSP"
    vendor_target_file = "vendor_manifest.xml"
    qssi_target_file = "qssi_manifest.xml"
    qnx_target_file = "qnx_manifest.xml"
    repo_path = ""

    download_manifest(artifactory_url, artifactory_token, vendor_source_file, vendor_target_file)
    download_manifest(artifactory_url, artifactory_token, qssi_source_file, qssi_target_file)
    download_manifest(artifactory_url, artifactory_token, qnx_source_file, qnx_target_file)

    create_branches_from_manifest(vendor_target_file, GITLAB_TOKEN, GITLAB_URL, base_repo_path, new_branch)
    create_branches_from_manifest(qssi_target_file, GITLAB_TOKEN, GITLAB_URL, base_repo_path, new_branch)
    create_branches_from_manifest(qnx_target_file, GITLAB_TOKEN, GITLAB_URL, repo_path, new_branch)
