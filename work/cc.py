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

FILE1 = "mr_sys_info.json"
def fetch_mrs_with_ready_to_sys_staging(group_url, private_token, file_name=FILE1):
    """
    获取指定GitLab组下所有状态为'open'且带有'ready_to_sys_staging'标签的Merge Requests，
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
            "labels": "ready_to_sys_staging",  # 只获取带有'ready_to_sys_staging'标签的MR
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


def get_unique_repo_dir(repo_url):
    parsed = urlparse(repo_url)
    path = parsed.path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]
    safe_path = path.replace('/', '_')
    return safe_path


def code_sync(mr_info_list, fallback_branch="8295_master"):
    """代码同步主函数"""
    print("====================== begin git merge ======================")
    
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)

    for repo_url, mr_list in mr_info_list.items():
        if not mr_list:
            print(f"⚠️ 仓库 {repo_url} 没有 MR 信息，跳过")
            continue
            
        repo_dir = get_unique_repo_dir(repo_url)
        local_path = os.path.join(WORK_DIR, repo_dir)
        
        # 获取基础信息
        base_branch = mr_list[0]["target_branch"]
        
        # 初始化或更新仓库
        if not init_or_update_repo(repo_url, local_path, base_branch, fallback_branch):
            continue
        
        print(f"\n📦 处理仓库：{repo_url}（共 {len(mr_list)} 个 MR）")
        
        # 步骤1: 检查所有MR与主分支的冲突
        os.chdir(local_path)
        mrs_conflict_with_master = check_all_mrs_with_master(mr_list, fallback_branch)
        os.chdir(root_path)
        
        if mrs_conflict_with_master:
            print(f"❌ 以下 MR 与主分支存在冲突，请先解决：")
            for mr_url in mrs_conflict_with_master:
                print(f"   - {mr_url}")
            continue
        
        # 步骤2: 检查MR之间的冲突
        if len(mr_list) > 1:
            print(f"🔍 检查 {len(mr_list)} 个 MR 之间的冲突...")
            os.chdir(local_path)
            check_conflict(mr_list, fallback_branch)
            os.chdir(root_path)
        else:
            print(f"✅ 只有单个 MR，跳过 MR 间冲突检查")

    print("====================== git merge end ======================")


def init_or_update_repo(repo_url, local_path, base_branch, fallback_branch):
    """初始化或更新仓库，返回是否成功"""
    try:
        if os.path.exists(local_path):
            os.chdir(local_path)
            run_cmd('git fetch origin')
            run_cmd(f'git reset --hard origin/{fallback_branch}')
            return True
        else:
            print(f"📥 初始化克隆仓库 {repo_url}")
            clone_cmd = f'git clone -b {base_branch} {repo_url}.git {local_path}'
            result = run_cmd(clone_cmd)
            if result.returncode != 0:
                print(f"❌ 克隆仓库失败：{repo_url}")
                return False
            return True
    except Exception as e:
        print(f"❌ 仓库初始化失败 {repo_url}: {e}")
        return False
    finally:
        if 'root_path' in globals():
            os.chdir(root_path)


def check_all_mrs_with_master(mr_list, fallback_branch):
    """检查所有MR与主分支的冲突，返回存在冲突的MR URL列表"""
    conflicts = []
    
    try:
        # 确保在主分支上
        run_cmd(f'git checkout -b {fallback_branch} origin/{fallback_branch}')
        
        for mr in mr_list:
            source_branch = mr.get("source_branch")
            web_url = mr.get("web_url")
            
            print(f"检查 MR: {source_branch}")
            
            # 尝试合并到主分支
            res = run_cmd(f"git merge origin/{source_branch} --allow-unrelated-histories --no-edit")
            
            if res.returncode != 0:
                conflicts.append(web_url)
                print(f"🔥 与主分支冲突")
                # 中止合并，回退到干净状态
                run_cmd("git merge --abort")
                run_cmd(f"git reset --hard origin/{fallback_branch}")
            else:
                print(f"✅ 与主分支无冲突")
                # 重置到主分支，为下一个MR做准备
                run_cmd(f"git reset --hard origin/{fallback_branch}")
        
        return conflicts
        
    except Exception as e:
        print(f"❌ 检查 MR 与主分支冲突时出错: {e}")
        return conflicts
        

def get_modified_files(branch, base_branch="8295_master"):
    """获取分支相对于基准分支修改的文件列表"""
    cmd = f"git diff --name-only origin/{branch} origin/{base_branch}"
    result = run_cmd(cmd)
    if result.returncode != 0:
        return set()
    return set(result.stdout.strip().splitlines()) if result.stdout else set()


def has_file_overlap(branch1, branch2, base_branch="8295_master"):
    """检查两个分支是否有文件重叠"""
    files1 = get_modified_files(branch1, base_branch)
    files2 = get_modified_files(branch2, base_branch)
    overlap = files1 & files2
    
    if overlap:
        print(f"📝 重叠文件数: {len(overlap)}")
        if len(overlap) <= 5:
            print(f"   文件列表: {', '.join(overlap)}")
        else:
            print(f"   文件列表(前5个): {', '.join(list(overlap)[:5])}...")
    
    return bool(overlap)


def check_conflict(mr_list, fallback_branch):
    if len(mr_list) <= 1:
        # check_conflict_with_master(mr_list, fallback_branch)
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

    check_conflict(mr_list[1:], fallback_branch)

def temp_merge(target_branch,source_branch1,source_branch2,web_url1,web_url2,author1,author2, fallback_branch="8295_master"):
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
            run_cmd(f"git reset --hard origin/{fallback_branch}")
        else:
            print("✅合并成功！")
    except Exception as e:
        print(f"合并操作异常：{e}")
    finally:
        # print(f"回到目标分支：{target_branch}")
        run_cmd(f"git checkout {target_branch}")
        run_cmd(f"git reset --hard origin/{fallback_branch}")
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
    fetch_mrs_with_ready_to_sys_staging(group_url, private_token)
 
    mr_list = get_mrs_info()
    code_sync(mr_list)
