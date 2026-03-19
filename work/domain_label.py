# 查询domain::*标签，open状态的MR信息，并检查是否存在冲突
import re
import requests
import json
import sys
from collections import defaultdict
import os
from urllib.parse import urlparse
import subprocess
import pandas as pd
from datetime import datetime
from GitLabMRFetcher import GitLabMRFetcher



# GitLab配置
GITLAB_URL = "https://git.sb.com/api/v4"
GROUP_PATH = "RSE"  # 组路径
PRIVATE_TOKEN = "sb"  # 替换为你的个人访问令牌
# 全局变量：存储冲突记录的表格
conflict_records = []
root_dir = os.getcwd()


def run_cmd(cmd, cwd=None):
    #print(f"{cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return result

def git_clone(web_url):
    cmd = f'git clone {web_url} '
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def get_data(domain_labels):
    son_mrs_dict = defaultdict(list)  # 使用 defaultdict 自动初始化空列表

    for label in domain_labels:  
        mrs = fetcher.get_filtered_son_mrs(label)  
        for mr in mrs:
            web_url = mr.get('web_url')
            repo_name = re.sub(r"/-/merge_requests/\d+", "", web_url)
            if repo_name:
                son_mrs_dict[repo_name].append(mr)  # 按 repo_name 分组存储

     # 打印统计信息
    for repo_name, mr_list in son_mrs_dict.items():
        if len(mr_list) <= 1:
            continue    
        else:
            print(f"\n仓库 {repo_name} 共有 {len(mr_list)} 个 MR:")
            code_sync(mr_list)

    # 写入符合条件的 MR 到文件
    with open("mr_info.json", "w", encoding="utf-8") as f:
        json.dump(son_mrs_dict,f, indent=4, ensure_ascii=False)

    return son_mrs_dict

def code_sync(mr_list,fallback_branch="8295_master"):
    work_dir="repos_domain"
    root_dir = os.getcwd()

    def safe_chdir(path):
        try:
            os.chdir(path)
        except Exception as e:
            print(f"❌ 目录切换失败: {path}, 错误: {e}")

    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    for mr in mr_list:
        base_branch = mr.get('target_branch')
        repo_url = re.sub(r"/-/merge_requests/\d+", "", mr.get('web_url'))
        source_branch = mr.get("source_branch")
        web_url = mr.get("web_url")
        # 本地path名称
        p_name = repo_url.rstrip('/').split('/')[-1]
        local_path = os.path.join(work_dir, p_name)

        if os.path.exists(local_path):
            os.chdir(local_path)
            run_cmd(f'git fetch origin')
            run_cmd(f'git reset --hard origin/{fallback_branch}')
            os.chdir(root_dir)
        else:
            # 克隆仓库
            clone_cmd = f'git clone -b {base_branch} {repo_url}.git {local_path}'
            result = run_cmd(clone_cmd)
            # 克隆失败跳过
            if result.returncode != 0:
                continue


        # TODO 合并到主分支，看是否和主分支存在冲突
        # 对iid进行从小到大排序，然后merge到主分支，把有冲突的web_url列出来  
        safe_chdir(local_path)

        run_cmd(f'git checkout -B {base_branch} origin/{base_branch}')
        res = run_cmd(f"git merge origin/{source_branch} --allow-unrelated-histories --no-edit")
        if res.returncode != 0:
            print("🔥和master merge有冲突：",web_url)
            run_cmd(f"git merge --abort")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
            continue
            
        safe_chdir(root_dir)
    #os.chdir(local_path)
    check_conflict(mr_list, fallback_branch=fallback_branch)
    #os.chdir(root_dir)


def has_conflict_with_master(mr_info):
    MR_IID = mr_info.get('iid')
    PROJECT_ID = mr_info.get("project_id")
    request_url = f"{GITLAB_URL}/projects/{PROJECT_ID}/merge_requests/{MR_IID}"

    try:
        response = requests.get(request_url, headers={"PRIVATE-TOKEN": PRIVATE_TOKEN})
        if response.status_code == 200:
            return response.json().get("has_conflicts", False)
    except Exception as e:
        print(f"✅ MR 状态中无冲突！")
    return True  # 默认保守处理


def has_file_overlap(branch1, branch2):
    print(branch1,branch2)
    cmd1 = f"git diff --name-only origin/{branch1} origin/8295_master"
    cmd2 = f"git diff --name-only origin/{branch2} origin/8295_master"
    #print(cmd1,cmd2)
    # 比较两个分支修改的文件是否有交集
    files1 = run_cmd(f"git diff --name-only origin/{branch1} origin/8295_master").stdout.strip().splitlines()
    files2 = run_cmd(f"git diff --name-only origin/{branch2} origin/8295_master").stdout.strip().splitlines()
    return bool(set(files1) & set(files2))


def check_conflict(mr_list,fallback_branch="8295_master"):  
    if len(mr_list) <= 1:
        return 0

    for index,a_mr_info in enumerate(mr_list):
        # 判断MR与库里的MASTER是否存在冲突
        if has_conflict_with_master(a_mr_info):
            print(f"🔥 与 master 存在冲突: {a_mr_info.get('web_url')}")
            run_cmd("git merge --abort")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
            continue
             
        if index == 0:
            continue

        print(mr_list[0]["source_branch"] + " merge " + mr_list[index]["source_branch"])
                
        #TODO git diff origin/APRICOT-777329_fix origin/8295_master --name-only 
        if not has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]):
            print(f"✅ 两个 MR 修改文件无重叠，跳过合并模拟")
            continue 
        #TODO 如果两个MR中没有修改相同的文件，不执行下面的git merge 操作

        begin_merge(
        mr_list[0]["target_branch"],mr_list[0]["source_branch"],mr_list[index]["source_branch"],
        mr_list[0]["web_url"],mr_list[index]["web_url"],
        mr_list[0]["author"],mr_list[index]["author"])

    check_conflict(mr_list[1:])


def begin_merge(target_branch, source_branch1, source_branch2,
                web_url1, web_url2, author1, author2, fallback_branch="8295_master"):
    try:
        print(f"🔁 切换并拉取分支：{source_branch1}")
        run_cmd(f"git checkout -B {source_branch1} origin/{source_branch1}")

        print(f"🔀 合并分支：{source_branch2} 到 {source_branch1}")
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
                "conflict_files": "get_conflict_files()"  # ⚠️ 用户需实现该函数
            }

            print("🔥 合并冲突检测到！")
            print(f"📍 {web_url1} vs {web_url2}")
            print(f"👤 作者冲突: {author1} vs {author2}")
            print(f"🗂️ 冲突文件: {conflict_info['conflict_files']}")
            
            # 回退合并
            run_cmd("git merge --abort")
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        else:
            print("✅ 合并成功！")

    except Exception as e:
        print(f"❌ 合并操作异常：{e}")
    finally:
        print(f"🔚 回到目标分支：{target_branch}")
        run_cmd(f"git checkout {target_branch}")
        print(f"🧹 删除临时分支：{source_branch1}")
        run_cmd(f"git branch -D {source_branch1}")


if __name__ == "__main__":
    root_path=os.getcwd()
    print("开始获取并过滤MR信息...")
    fetcher = GitLabMRFetcher(GITLAB_URL, GROUP_PATH, PRIVATE_TOKEN)
    domain_labels = fetcher.get_filtered_domain_labels()

    print(f"共找到 {len(domain_labels)} 个符合条件的子MR label")
    get_data(domain_labels)
    

