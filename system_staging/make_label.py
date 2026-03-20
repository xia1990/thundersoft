##############################################
#此脚本用于给MR打integrated_E231.0-25.4的label.#
##############################################


import requests
import json
import sys
import re
from urllib.parse import quote,urljoin


TARGET_BRANCH = "8295_master"  
GROUP_PATH = "sb"


# 查询open状态，并且带有ready_to_sys_staging label的MR信息
def get_domain_labels(GITLAB_URL,GROUP_PATH,ACCESS_TOKEN):
    all_mrs_info = []
    page = 1
    per_page = 100  # 每页最大数量
    
    while True:
        # 构建API请求URL
        url = f"{GITLAB_URL}/api/v4/groups/{GROUP_PATH}/merge_requests"
         # 请求头
        headers = {
            "PRIVATE-TOKEN": ACCESS_TOKEN
        } 
        # 请求参数
        params = {
            "state": "opened",
            "scope": "all",
            "page": page,
            "per_page": per_page,
            "labels": "ready_to_sys_staging" 
        }
        
       
        # 发送GET请求
        response = requests.get(url, params=params, headers=headers)       
        if response.status_code != 200:
            print(f"请求失败，状态码: {response.status_code}")
            print(response.text)
            break
        
        mrs = response.json()
        if not mrs:
            break
            
        # 提取所需信息
        for mr in mrs:
                       
            mr_info = {
                "mr_iid": mr.get("iid"),
                "project_id": mr.get("project_id"),
                "web_url": mr.get("web_url"),
                "labels": mr.get("labels", [])
            }
            all_mrs_info.append(mr_info)
                  
        page += 1
        
        # 检查是否有更多页
        if 'next' not in response.links:
            break
    # 写入符合条件的 MR 到文件
    with open("filtered_mrs.json", "w", encoding="utf-8") as f:
        json.dump(all_mrs_info,f, indent=4, ensure_ascii=False)

    return all_mrs_info


# 给MR添加label
def add_label_to_mr(all_mrs_info):
    NEW_LABEL = "integrated_E231.0-25.4"

    # 解析json文件
    with open("filtered_mrs.json", "r", encoding="utf-8") as f:
        mrs_data = json.load(f) 
        # 遍历读取的数据信息
        for mr in mrs_data:
            project_id = mr.get("project_id")
            mr_iid = mr.get("mr_iid")
            repo_url = mr.get("web_url")

            # 得到要添加label的MR的url连接
            mr_url = urljoin(GITLAB_URL, f"api/v4/projects/{project_id}/merge_requests/{mr_iid}")
            headers = {
                "PRIVATE-TOKEN": ACCESS_TOKEN
            }

            try:
                response = requests.get(mr_url, headers=headers)
                response.raise_for_status()
                mr_data = response.json()
                current_labels = set(mr_data.get("labels", []))
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] 获取 MR 信息失败 ({repo_url}): {e}")
                continue

            if NEW_LABEL in current_labels:
                print(f"[SKIP] MR 已包含标签 '{NEW_LABEL}'，跳过: {repo_url}")
                continue

            updated_labels = current_labels.union({NEW_LABEL})
            label_str = ",".join(updated_labels)

            try:
                update_data = {"labels": label_str}
                # 添加label的命令
                response = requests.put(mr_url, headers=headers, data=update_data)
                response.raise_for_status()
                print(f"[SUCCESS] 成功为 {repo_url} 添加标签: {NEW_LABEL}")
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] 更新 MR 标签失败 ({repo_url}): {e}")


if __name__ == "__main__":
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")
    ACCESS_TOKEN = config.get("gitlab","token")
    GITLAB_URL = config.get("gitlab","url")
    # === 配置信息 ===
    # 这里会得到去掉domain::后的label
    all_mrs_info = get_domain_labels(GITLAB_URL, GROUP_PATH, ACCESS_TOKEN)    
    add_label_to_mr(all_mrs_info)
    write_excel(all_mrs_info)
