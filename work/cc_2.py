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

FILE1 = "mr_sys_info.json"
def fetch_mrs_with_ready_to_sys_mrqg(group_url, private_token, file_name=FILE1):
    """
    获取指定GitLab组下所有状态为'open'且带有'ready_to_sys_mrqg'标签的Merge Requests，
    并将其所有信息保存到一个JSON文件中。
    
    :param group_url: GitLab组的API基础URL（不包含API版本和路径）
    :param private_token: GitLab私有token，用于身份验证
    :param file_name: 保存JSON数据的文件名，默认为"mr_sys_info.json"
    """
    # GitLab API的基础URL
    api_url = f"{group_url}/merge_requests"
    
    # 请求头部，包含私有token进行身份验证
    headers = {
        "Private-Token": private_token
    }
    
    # 存储符合条件的MR
    filtered_mrs = []

    # 发起请求获取Merge Requests列表
    page = 1
    while True:
        # 请求带有分页参数，避免一次性加载过多数据
        response = requests.get(api_url, headers=headers, params={
            "state": "opened",               # 只获取状态为'opened'的MR
            "labels": "ready_to_sys_mrqg",  # 只获取带有'ready_to_sys_staging'标签的MR
            "page": page,                    # 分页参数
            "per_page": 100                  # 每页返回100个MR，具体根据实际情况调整
        })
        
        # 如果请求成功
        if response.status_code == 200:
            mrs = response.json()
            
            # 如果没有更多数据，跳出循环
            if not mrs:
                break

            # 将符合条件的MR添加到结果列表中
            for mr in mrs:
                filtered_mrs.append(mr)  # 直接添加MR的所有信息

            # 检查是否还有更多页面，如果有，继续请求
            page += 1
        else:
            print(f"请求失败，状态码: {response.status_code}")
            break

    # 将筛选后的MR写入JSON文件
    with open(file_name, "w", encoding="utf-8") as json_file:
        json.dump(filtered_mrs, json_file, ensure_ascii=False, indent=4)
    
    print(f"数据已保存，符合条件的MR总数：{len(filtered_mrs)}，已保存至文件 {file_name}")


def get_mrs_info():
    # 假设你已经将 JSON 文件加载为 Python 对象
    with open(FILE1, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 创建一个默认字典，仓库名称为key,把同一个仓库的MR 放入同一个列表中,mr信息为value
    grouped_mrs = defaultdict(list)

    # 提取字段并分类
    for mr in data:
        target_branch = mr['target_branch']
        #对目标分支不是8295_master分支的代码仓库进行特殊处理
        if target_branch != "8295_master":
            name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])
            print("0"*100)
            print(mr['web_url'])
            print("0"*100)
            # TODO : 执行git clone 操作 
            continue

        # 8295_master 的数据
        entry = {
            'iid': mr['iid'],
            'web_url': mr['web_url'],
            'source_branch': mr['source_branch'],
            'target_branch': mr['target_branch'],
            'author': mr['author']['username']
        }
        name = re.sub(r'/-/merge_requests/\d+', '', mr['web_url'])
        
        grouped_mrs[name].append(entry)
    # 按 iid 升序排序每个项目组内的 MR
    for iid in grouped_mrs:
        grouped_mrs[iid].sort(key=lambda x: x['iid'])

    return grouped_mrs


def code_sync(mr_info_list, fallback_branch="8295_master"):
    print("======================begin git merge ======================")
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)
    # else:
    #    shutil.rmtree(WORK_DIR)
    #    os.makedirs(WORK_DIR)

    for repo_url, mr_list in mr_info_list.items():
        if len(mr_list) <= 1:
            #print(f"仓库：{repo_url} 有 {len(mr_list)} 个 MR")
            continue  # 跳过只有一个 MR 的仓库

        repo_name = repo_url.rstrip('/').split('/')[-1]
        print(f"仓库：{repo_name} 有 {len(mr_list)} 个 MR")
        repo_name = repo_url.rstrip('/').split('/')[-1]
        local_path = os.path.join(WORK_DIR, repo_name)
        web_url = mr_list[0]["web_url"]
        source_branch = mr_list[0]["source_branch"]
        base_branch = mr_list[0]["target_branch"]

        if os.path.exists(local_path):
            # 如果本地有代码，则删除
            # shutil.rmtree(local_path)
            os.chdir(local_path)
            run_cmd(f'git fetch origin')
            run_cmd(f'git reset --hard origin/{fallback_branch}')
            os.chdir(root_path)
        else:
            print("Init clone repos")
            # 克隆仓库
            clone_cmd = f'git clone -b {base_branch} {repo_url}.git {local_path}'
            result = run_cmd(clone_cmd)
            if result.returncode != 0:
                continue  # clone失败则跳

        # 对iid进行从小到大排序，然后merge到主分支，把有冲突的web_url列出来
        os.chdir(local_path)
        # TODO 合并到主分支，看是否和主分支存在冲突
        check_conflict_with_master(mr_list, fallback_branch)
        os.chdir(root_path)

        # 两两merge进行冲突检测
        # 这里一定要进到每个仓库里面
        os.chdir(local_path)
        check_conflict(mr_list)
        os.chdir(root_path)


def check_conflict_with_master(mr_list, fallback_branch):
    cmd1 = f'git checkout -b {fallback_branch} origin/{fallback_branch}'
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
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        

def has_file_overlap(branch1, branch2):
    # 对比两个远程分支修改的文件
    cmd1 = f"git diff --name-only origin/{branch1} origin/i2_max_8295_master"
    cmd2 = f"git diff --name-only origin/{branch2} origin/i2_max_8295_master"
    #print(cmd1,cmd2)
    # 比较两个分支修改的文件是否有交集
    files1 = run_cmd(cmd1).stdout.strip().splitlines()
    files2 = run_cmd(cmd2).stdout.strip().splitlines()
    return bool(set(files1) & set(files2))


def check_conflict(mr_list):
    if len(mr_list) <= 1:
        return 0
    for index,a_mr_info in enumerate(mr_list):
        # 自己和自己merge
        if index == 0:
            continue

        print("\033[1;32m~\033[0m"*100)
        print(mr_list[0]["source_branch"] + "\033[1;34m merge \033[0m " + mr_list[index]["source_branch"])
        print("\033[1;32m~\033[0m"*100)
        #TODO git diff origin/APRICOT-777329_fix origin/8295_master --name-only  
        #TODO 如果两个MR中没有修改相同的文件，不执行下面的git merge 操作
        print(has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]))
        if not has_file_overlap(mr_list[0]["source_branch"], mr_list[index]["source_branch"]):
            print(f"✅ 两个 MR 修改文件无重叠，跳过合并模拟")
            continue 

        temp_merge(
        mr_list[0]["target_branch"],mr_list[0]["source_branch"],mr_list[index]["source_branch"],
        mr_list[0]["web_url"],mr_list[index]["web_url"],
        mr_list[0]["author"],mr_list[index]["author"])

    check_conflict(mr_list[1:])

def temp_merge(target_branch,source_branch1,source_branch2,web_url1,web_url2,author1,author2, fallback_branch="i2_max_8295_master"):
    try:
        print(f"切换并拉取分支：{source_branch1}")
        run_cmd(f"git checkout -B {source_branch1} origin/{source_branch1}")

        print(f"合并分支：{source_branch2} 到 {source_branch1}")
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
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        else:
            print("✅合并成功！")
    except Exception as e:
        print(f"合并操作异常：{e}")
    finally:
        print(f"回到目标分支：{target_branch}")
        run_cmd(f"git checkout {target_branch}")
        run_cmd(f"git reset --hard origin/{fallback_branch}")
        print(f"⚠️删除临时分支：{source_branch1}")
        run_cmd(f"git branch -D {source_branch1}")


def run_cmd(cmd, cwd=None):
    #print(f"{cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return result


# 示例调用
if __name__ == "__main__":
    root_path=os.getcwd()
    WORK_DIR = "repos_i2"
    
    # 加载环境变量
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")
    private_token = config.get("gitlab","token")
    group_url_android = "https://git.sb.com/api/v4/groups/apricot-android-mb"
    group_url_qnx = "https://git.sb.com/api/v4/groups/apricot-qnx-mb"
    # 检查android侧冲突
    fetch_mrs_with_ready_to_sys_mrqg(group_url_android, private_token)
    mr_list = get_mrs_info()
    code_sync(mr_list)
    # 检查qnx侧冲突
    print("\033[1;31m 开始检查QNX侧冲突 \033[0m")
    print("\033[1;31m 开始检查QNX侧冲突 \033[0m")
    fetch_mrs_with_ready_to_sys_mrqg(group_url_qnx, private_token)
    mr_list = get_mrs_info()
    code_sync(mr_list)
