#!/usr/bin/python3

import os
import requests
import json
import sys
from configparser import ConfigParser



def run_cmd(cmd, cwd=None):
    #print(f"{cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return result

file = "sys_mrs.json"
def find_sys_mrs(group_url, private_token, file_name=file):
    """
    获取指定GitLab组下所有状态为'open'且带有'ready_to_sys_staging'标签的Merge Requests，
    并将其所有信息保存到一个JSON文件中。
    
    :param group_url: GitLab组的API基础URL（不包含API版本和路径）
    :param private_token: GitLab私有token，用于身份验证
    :param file_name: 保存JSON数据的文件名，默认为"mrs_ready_to_staging.json"
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


def check_branch(file):
    with open(file, 'r', encoding='utf-8') as f1:
        data = json.load(f1)

    for mr in data:
        target_branch = mr.get('target_branch')
        if target_branch != "8295_master":

            print("🔥 ",mr.get('web_url')," : ",mr.get('author')['username'])
    

if __name__=="__main__":
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")
    group_url = config.get("gitlab","group")
    private_token = config.get("gitlab","token")
    find_sys_mrs(group_url, private_token, file_name=file)
    check_branch(file)