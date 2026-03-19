import requests
import json
import os
import sys
import subprocess
import re
from collections import defaultdict
import shutil
import re
import pprint
import time
from configparser import ConfigParser
from datetime import datetime
import hashlib
from urllib.parse import urlparse
from collections import defaultdict
import urllib.parse
import urllib.parse


FILE1 = "mr_sys_info.json"
def fetch_mrs_with_ready_to_sys_staging_pending(group_url, private_token):
    api_url = f"{group_url}/merge_requests"
    headers = {"Private-Token": private_token}
    all_mrs_info = {}
    son_mrs = []
    page = 1

    while True:
        response = requests.get(api_url, headers=headers, params={
            "state": "opened",
            "labels": "ready_to_sys_staging_pending",
            "page": page,
            # "target_branch": main_branch,
            "per_page": 100
        })

        if response.status_code != 200:
            print(f"请求失败，状态码: {response.status_code}")
            break

        mrs = response.json()
        if not mrs:
            break

        for mr in mrs:
            # 主MR的web_url
            main_url = mr.get("web_url")
            description = mr.get('description', '')
            # 提取 Crosslink Merge Requests 到 Domain
            match = re.search(r"Crosslink Merge Requests:\s*(.*?)\s*Domain:", description, re.S)
            if match:
                section = match.group(1)
                # 主MR包含的子MR，去重
                son_urls = list(set(re.findall(r"https://git\.sb\.com[^\s]+/merge_requests/\d+", section)))
            else:
                son_urls = []

            all_mrs_info[main_url] = {
                "son_mrs": son_urls
            }

        page += 1
    return all_mrs_info


def fetch_simple_mrs_by_urls(mr_url_list, private_token, file_name=FILE1):
    headers = {"Private-Token": private_token}

    # 按仓库分组
    grouped_mrs = defaultdict(list)

    for mr_url in mr_url_list:
        match = re.search(
            r"https://git\.sb\.i\.sb\.com/(.*?)/-/merge_requests/(\d+)",
            mr_url,
            re.I
        )
        if not match:
            print(f"URL 不合法，跳过：{mr_url}")
            continue

        project_path = match.group(1)
        mr_iid = match.group(2)

        # API 项目路径编码
        encoded_project = urllib.parse.quote_plus(project_path)

        api_url = (
            f"https://git.sb.com/api/v4/projects/"
            f"{encoded_project}/merge_requests/{mr_iid}"
        )

        resp = requests.get(api_url, headers=headers)

        if resp.status_code != 200:
            print(f"请求失败: {resp.status_code} -> {api_url}")
            continue

        mr = resp.json()
        target_branch = mr['target_branch']
        #对目标分支不是8295_master分支的代码仓库进行特殊处理
        if target_branch != main_branch:
            name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])
            print("~"*100)
            print("目标分支不是：8295_master!=>", mr['web_url'])
            print("~"*100)
            # TODO : 执行git clone 操作 
            continue

        # ---------- 构造 entry ----------
        entry = {
            'iid': mr.get('iid'),
            'web_url': mr.get('web_url'),
            'source_branch': mr.get('source_branch'),
            'target_branch': mr.get('target_branch'),
            'author': mr.get('author', {}).get('username')
        }

        # ---------- 解析仓库地址 ----------
        # 从 web_url 去掉 "/-/merge_requests/xxx"
        repo_name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])

        # ---------- 加入分组 ----------
        grouped_mrs[repo_name].append(entry)

    # ---- 每个仓库内按 iid 排序 ----
    for repo in grouped_mrs:
        grouped_mrs[repo].sort(key=lambda x: x['iid'])

    # ---- 可选：保存 JSON ----
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(grouped_mrs, f, ensure_ascii=False, indent=4)

    print(f"共获取 {sum(len(v) for v in grouped_mrs.values())} 个 MR，已保存到 {file_name}")

    return grouped_mrs


def get_unique_repo_dir(repo_url):
    parsed = urlparse(repo_url)
    path = parsed.path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]
    safe_path = path.replace('/', '_')
    return safe_path


def code_sync(mr_info_list, main_branch):
    print("====================== begin git merge ======================")
    
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)

    for repo_url, mr_list in mr_info_list.items():
        repo_dir = get_unique_repo_dir(repo_url)
        local_path = os.path.join(WORK_DIR, repo_dir)

        web_url = mr_list[0]["web_url"]
        source_branch = mr_list[0]["source_branch"]
        base_branch = mr_list[0]["target_branch"]

        # print(f"处理仓库：{repo_url}（本地路径：{repo_dir}）")

        if os.path.exists(local_path):
            os.chdir(local_path)
            run_cmd(f'git fetch origin')
            run_cmd(f'git reset --hard origin/{main_branch}')
            os.chdir(root_path)
        else:
            print(f"初始化克隆仓库 {repo_url}")
            clone_cmd = f'git clone -b {base_branch} {repo_url}.git {local_path}'
            result = run_cmd(clone_cmd)
            if result.returncode != 0:
                print(f"❌ 克隆仓库失败：{repo_url}")
                continue

        if len(mr_list) <= 1:
            # print(f"仓库：{repo_url} 只有 {len(mr_list)} 个 MR，检测与主分支冲突...")
            os.chdir(local_path)
            check_conflict_with_master(mr_list, main_branch)
            os.chdir(root_path)
            continue

        print(f"仓库：{repo_url} 有 {len(mr_list)} 个 MR，检测 MR 之间冲突...")
        os.chdir(local_path)
        check_conflict(mr_list, main_branch)
        os.chdir(root_path)

    print("====================== git merge end ======================")


def check_conflict_with_master(mr_list, main_branch):
    cmd1 = f'git checkout -b {main_branch} origin/{main_branch}'
    result = run_cmd(cmd1)

    for mr in mr_list:
        source_branch = mr.get("source_branch")
        web_url = mr.get("web_url")
        # print("-"*100)
        # print(source_branch)
        # print("-"*100)
        # 和 master 分支进行 merge
        res = run_cmd(f"git merge origin/{source_branch} --allow-unrelated-histories --no-edit")
        if res.returncode != 0:
            print("-"*100)
            print("\033[1;31m🔥和master merge有冲突：\033[0m",web_url)
            print("-"*100)
            run_cmd(f"git merge --abort")
            run_cmd(f"git reset --hard origin/{main_branch}")
        else:
            print("✅和 8295_master 合并成功！")
        

def has_file_overlap(branch1, branch2):
    # 对比两个远程分支修改的文件
    cmd1 = f"git diff --name-only origin/{branch1} origin/{main_branch}"
    cmd2 = f"git diff --name-only origin/{branch2} origin/{main_branch}"
    #print(cmd1,cmd2)
    # 比较两个分支修改的文件是否有交集
    files1 = run_cmd(cmd1).stdout.strip().splitlines()
    files2 = run_cmd(cmd2).stdout.strip().splitlines()
    return bool(set(files1) & set(files2))


def check_conflict(mr_list, main_branch):
    if len(mr_list) <= 1:
        check_conflict_with_master(mr_list, main_branch)
        return 0
    for index,a_mr_info in enumerate(mr_list):
        # 自己和自己merge
        if index == 0:
            continue

        print("\033[1;32m~\033[0m"*100)
        print(mr_list[0]["source_branch"] + "\033[1;34m merge \033[0m " + mr_list[index]["source_branch"])
        print("\033[1;32m~\033[0m"*100)
        # TODO git diff origin/APRICOT-777329_fix origin/8295_master --name-only  
        # TODO 如果两个MR中没有修改相同的文件，不执行下面的git merge 操作
        print(has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]))
        if not has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]):
            print(f"✅ 两个 MR 修改文件无重叠，跳过合并模拟")
            continue 

        temp_merge(
        mr_list[0]["target_branch"],mr_list[0]["source_branch"],mr_list[index]["source_branch"],
        mr_list[0]["web_url"],mr_list[index]["web_url"],
        mr_list[0]["author"],mr_list[index]["author"])

    check_conflict(mr_list[1:], main_branch)

def temp_merge(target_branch,source_branch1,source_branch2,web_url1,web_url2,author1,author2):
    try:
        # print(f"切换并拉取分支：{source_branch1}")
        run_cmd(f"git checkout -B {source_branch1} origin/{source_branch1}")

        # print(f"合并分支：{source_branch2} 到 {source_branch1}")
        merge_result = run_cmd(f"git merge origin/{source_branch2} --allow-unrelated-histories --no-edit")

        if merge_result.returncode != 0:
            # 合并冲突处理
            conflict_info = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target_branch": target_branch,
                "source_branch1": source_branch1,
                "source_branch2": source_branch2,
                "web_url1": web_url1,
                "web_url2": web_url2,
                "author1": author1,
                "author2": author2,
                "conflict_files": merge_result.stderr 
            }
            print("\033[1;31m 🔥合并冲突检测到! \033[0m")
            print(f"{web_url1} vs {web_url2}")
            print(f"🔥作者冲突: {author1} vs {author2}")
            print(f"🔥冲突文件: {conflict_info['conflict_files']}")
                
            # 回退合并
            run_cmd(f"git merge --abort")
            run_cmd(f"git reset --hard origin/{main_branch}")
        else:
            print("✅合并成功！")
    except Exception as e:
        print(f"合并操作异常：{e}")
    finally:
        # print(f"回到目标分支：{target_branch}")
        run_cmd(f"git checkout {target_branch}")
        run_cmd(f"git reset --hard origin/{main_branch}")
        # print(f"⚠️删除临时分支：{source_branch1}")
        run_cmd(f"git branch -D {source_branch1}")


def run_cmd(cmd, cwd=None):
    #print(f"{cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return result


# 示例调用
if __name__ == "__main__":
    root_path=os.getcwd()
    WORK_DIR = "repos"
    
    # 加载环境变量
    config = ConfigParser()
    config.read("/home/gayuxia/config.ini")
    group_url = config.get("gitlab","group")
    private_token = config.get("gitlab","token")
    main_branch = "8295_master"
    #得到所有主MR和子MR
    mr_urls = fetch_mrs_with_ready_to_sys_staging_pending(group_url, private_token)
    # 存放所有mr的列表
    mr_url_list = []
    for k,v in mr_urls.items():
        for a,b in v.items():
            for url in b:
                mr_url_list.append(url)
    # 得到本次要检查的MR列表
    mr_list = fetch_simple_mrs_by_urls(mr_url_list, private_token, file_name=FILE1)
    code_sync(mr_list, main_branch)
