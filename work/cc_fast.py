#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import json
import os
import sys
import subprocess
import re
from collections import defaultdict
import shutil
import pprint
import time
from configparser import ConfigParser
from datetime import datetime
from urllib.parse import urlparse

# ==========================================================
# 全局缓存
# ==========================================================
DIFF_CACHE = {}
FILE1 = "mr_sys_info.json"


# ==========================================================
# 优化版 requests 调用（Session 复用）
# ==========================================================
def fetch_mrs_with_ready_to_sys_staging(group_url, private_token, file_name=FILE1):
    """
    获取指定GitLab组下所有状态为'open'且带有'ready_to_sys_staging'标签的Merge Requests，
    并将其所有信息保存到一个JSON文件中。
    """

    api_url = f"{group_url}/merge_requests"
    session = requests.Session()
    session.headers.update({"Private-Token": private_token})

    filtered_mrs = []
    page = 1

    while True:
        response = session.get(api_url, params={
            "state": "opened",
            "labels": "ready_to_sys_staging",
            "page": page,
            "per_page": 100
        }, timeout=30)

        if response.status_code == 200:
            mrs = response.json()
            if not mrs:
                break
            filtered_mrs.extend(mrs)
            page += 1
        else:
            print(f"请求失败，状态码: {response.status_code}")
            break

    with open(file_name, "w", encoding="utf-8") as json_file:
        json.dump(filtered_mrs, json_file, ensure_ascii=False, indent=4)

    print(f"✅ 数据已保存，符合条件的MR总数：{len(filtered_mrs)}，文件：{file_name}")


# ==========================================================
# 加载 MR 信息（保持原逻辑）
# ==========================================================
def get_mrs_info():
    with open(FILE1, 'r', encoding='utf-8') as f:
        data = json.load(f)

    grouped_mrs = defaultdict(list)
    for mr in data:
        target_branch = mr['target_branch']
        if target_branch != "8295_master":
            name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])
            print("0"*100)
            print(mr['web_url'])
            print("0"*100)
            continue

        entry = {
            'iid': mr['iid'],
            'web_url': mr['web_url'],
            'source_branch': mr['source_branch'],
            'target_branch': mr['target_branch'],
            'author': mr['author']['username']
        }
        name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])
        grouped_mrs[name].append(entry)

    for iid in grouped_mrs:
        grouped_mrs[iid].sort(key=lambda x: x['iid'])
    return grouped_mrs


# ==========================================================
# 优化版命令执行函数
# ==========================================================
def run_cmd(cmd, cwd=None):
    result = subprocess.run(
        cmd,
        # cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0 and result.stderr:
        sys.stderr.write(f"[WARN] 命令执行失败: {cmd}\n{result.stderr}\n")
    return result


# ==========================================================
# 缓存 diff 结果，避免重复 git diff
# ==========================================================
def get_diff_files(branch, base="origin/8295_master"):
    """缓存分支的 diff 文件"""
    if branch in DIFF_CACHE:
        return DIFF_CACHE[branch]
    result = run_cmd(f"git diff --name-only origin/{branch} {base}")
    DIFF_CACHE[branch] = set(result.stdout.strip().splitlines())
    return DIFF_CACHE[branch]


def has_file_overlap(branch1, branch2):
    """判断两个分支修改文件是否重叠"""
    files1 = get_diff_files(branch1)
    files2 = get_diff_files(branch2)
    return bool(files1 & files2)


def get_unique_repo_dir(repo_url):
    """
    根据完整仓库路径生成稳定唯一的本地目录名。
    示例：
    https://gitlab.company.com/teamA/group1/service.git -> teamA__group1__service
    https://gitlab.company.com/teamB/group1/service.git -> teamB__group1__service
    """
    parsed = urlparse(repo_url)
    path = parsed.path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]
    safe_path = path.replace('/', '_')
    return safe_path


def code_sync(mr_info_list, fallback_branch="8295_master"):
    print("====================== begin git merge ======================")
    
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)

    for repo_url, mr_list in mr_info_list.items():
        # 生成唯一、稳定的本地目录名
        repo_dir = get_unique_repo_dir(repo_url)
        local_path = os.path.join(WORK_DIR, repo_dir)

        # 提取 MR 信息
        web_url = mr_list[0]["web_url"]
        source_branch = mr_list[0]["source_branch"]
        base_branch = mr_list[0]["target_branch"]

        repo_display_name = repo_url.rstrip('/').split('/')[-1]
        # print(f"处理仓库：{repo_display_name}（本地路径：{repo_dir}）")

        # 如果本地仓库已存在，则更新并重置到 fallback 分支
        if os.path.exists(local_path):
            os.chdir(local_path)
            print(f"更新已有仓库：{repo_url}")
            run_cmd("git fetch origin")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
            os.chdir(root_path)
        else:
            # 初始化克隆
            print(f"初始化克隆仓库：{repo_url}")
            clone_cmd = f"git clone -b {base_branch} {repo_url}.git {local_path}"
            result = run_cmd(clone_cmd)
            if result.returncode != 0:
                print(f"❌ 克隆失败，跳过仓库：{repo_url}")
                continue

        # 进入仓库进行 MR 检查
        os.chdir(local_path)
        if len(mr_list) <= 1:
            # print(f"仓库：{repo_url} 只有 {len(mr_list)} 个 MR，检测与主分支冲突...")
            check_conflict_with_master(mr_list, fallback_branch)
        else:
            # print(f"仓库：{repo_url} 有 {len(mr_list)} 个 MR，检测 MR 之间冲突...")
            check_conflict(mr_list, fallback_branch)
        os.chdir(root_path)

    print("====================== git merge end ======================")


def check_conflict_with_master(mr_list, fallback_branch):
    # 检查是否已有该分支
    result = run_cmd(f"git branch --list {fallback_branch}")
    
    # 如果返回结果不为空，表示分支存在
    if result.stdout.strip():  # 使用 strip() 来去除多余的空白字符
        print(f"分支存在：{os.getcwd()}")
        # 切换到该分支并重置为远程版本
        run_cmd(f"git checkout {fallback_branch}")
        run_cmd(f"git reset --hard origin/{fallback_branch}")
    else:
        print(f"分支不存在：{os.getcwd()}")
        # 如果分支不存在，基于远程创建该分支
        run_cmd(f"git checkout -b {fallback_branch} origin/{fallback_branch}")

    for mr in mr_list:
        source_branch = mr.get("source_branch")
        web_url = mr.get("web_url")

        res = run_cmd(f"git merge origin/{source_branch} --allow-unrelated-histories --no-edit")
        if res.returncode != 0:
            print("-"*100)
            print("\033[1;31m🔥和master merge有冲突：\033[0m", web_url)
            print("-"*100)
            run_cmd(f"git merge --abort")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        else:
            print("✅和 master 合并成功！")
            # 这里会回退 master 代码到原始状态
            run_cmd(f"git reset --hard origin/{fallback_branch}")


def check_conflict(mr_list, fallback_branch):
    if len(mr_list) <= 1:
        check_conflict_with_master(mr_list, fallback_branch)
        return 0

    for index, a_mr_info in enumerate(mr_list):
        if index == 0:
            continue

        print("\033[1;32m~\033[0m"*100)
        print(mr_list[0]["source_branch"] + "\033[1;34m merge \033[0m " + mr_list[index]["source_branch"])
        print("\033[1;32m~\033[0m"*100)

        if not has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]):
            print(f"✅ 两个 MR 修改文件无重叠，跳过合并模拟")
            continue

        temp_merge(
            mr_list[0]["target_branch"], mr_list[0]["source_branch"], mr_list[index]["source_branch"],
            mr_list[0]["web_url"], mr_list[index]["web_url"],
            mr_list[0]["author"], mr_list[index]["author"])

    check_conflict(mr_list[1:], fallback_branch)


def temp_merge(target_branch, source_branch1, source_branch2,
               web_url1, web_url2, author1, author2, fallback_branch="8295_master"):
    try:
        run_cmd(f"git checkout -B {source_branch1} origin/{source_branch1}")
        merge_result = run_cmd(f"git merge origin/{source_branch2} --allow-unrelated-histories --no-edit")

        if merge_result.returncode != 0:
            print("\033[1;31m 🔥合并冲突检测到! \033[0m")
            print(f"{web_url1} vs {web_url2}")
            print(f"🔥作者冲突: {author1} vs {author2}")
            print(f"🔥冲突文件: {merge_result.stderr}")
            run_cmd(f"git merge --abort")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        else:
            print("✅合并成功！")
    except Exception as e:
        print(f"合并操作异常：{e}")
    finally:
        run_cmd(f"git checkout {target_branch}")
        run_cmd(f"git reset --hard origin/{fallback_branch}")
        run_cmd(f"git branch -D {source_branch1}")


# ==========================================================
# 主入口
# ==========================================================
if __name__ == "__main__":
    root_path = os.getcwd()
    WORK_DIR = "repos"

    config = ConfigParser()
    config.read("/home/gaoyuxia/config.ini")
    group_url = config.get("gitlab", "group")
    private_token = config.get("gitlab", "token")

    fetch_mrs_with_ready_to_sys_staging(group_url, private_token)
    mr_list = get_mrs_info()
    code_sync(mr_list)
