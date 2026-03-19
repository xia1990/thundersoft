import requests
import json
from typing import List, Dict
import os
from pathlib import Path


class GitLabMRQuery:
    def __init__(self, base_url: str, group_path: str, private_token: str):
        """
        初始化 GitLab MR 查询工具
        
        :param base_url: GitLab 基础 URL (e.g. "https://git.sb.com")
        :param group_path: 组路径 (e.g. "RSE")
        :param private_token: GitLab 私有访问令牌
        """
        self.base_url = base_url.rstrip('/')
        self.group_path = group_path.strip('/')
        self.private_token = private_token
        self.api_url = f"{self.base_url}/api/v4"
        
    def get_group_id(self) -> int:
        """获取组的 ID"""
        url = f"{self.api_url}/groups/{self.group_path}"
        headers = {"PRIVATE-TOKEN": self.private_token}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()["id"]
    
    def query_mrs(self, state: str = "opened", labels: List[str] = None) -> List[Dict]:
        """
        查询合并请求
        
        :param state: MR 状态 (opened/closed/merged/all)
        :param labels: 要筛选的标签列表
        :return: 合并请求列表
        """
        group_id = self.get_group_id()
        url = f"{self.api_url}/groups/{group_id}/merge_requests"
        
        headers = {"PRIVATE-TOKEN": self.private_token}
        params = {
            "state": state,
            "scope": "all",
            "per_page": 100  # 每页最大数量
        }
        
        if labels:
            params["labels"] = ",".join(labels)
        
        all_mrs = []
        page = 1
        
        while True:
            params["page"] = page
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            mrs = response.json()
            if not mrs:
                break
                
            all_mrs.extend(mrs)
            page += 1
            
        return all_mrs
    


    def filter_mr_info(self, mrs: List[Dict]) -> List[Dict]:
        """
        过滤 MR 信息，只保留需要的字段
        
        :param mrs: 合并请求列表
        :return: 过滤后的 MR 信息列表
        """
        filtered = []
        for mr in mrs:
            project_name = mr["references"]["relative"].split('!')[0].replace('RSE/android/aosp/', '')
            filtered.append({
                "web_url":mr["web_url"],
                "project_name": project_name,
                "relative": mr["references"]['relative'],
                "source_branch": mr["source_branch"],
                "target_branch": mr["target_branch"],
            })
        return filtered

    def find_local_path(self,project_name):
        """
        在本地文件系统中查找匹配的实际路径（大小写不敏感）
        
        :param project_name: 从 GitLab 获取的路径 (e.g. "vendor/mercedes/packages/mbaudio")
        :return: 本地实际存在的正确大小写路径
        """
        parts = project_name.split('/')
        current_path = os.getcwd()  # 或者从你的代码根目录开始
        
        for part in parts:
            # 列出当前目录下的所有文件和目录
            try:
                entries = os.listdir(current_path)
            except OSError:
                return None  # 路径不存在
            
            # 查找大小写不敏感匹配的目录
            matched = None
            for entry in entries:
                if entry.lower() == part.lower():
                    matched = entry
                    break
            
            if not matched:
                return None  # 没有找到匹配的目录
            
            current_path = os.path.join(current_path, matched)
        
        return current_path


    def resolve_local_path(self, project_name):
        """解析本地实际路径（处理大小写问题）"""
        # 这里可以使用上述任何一种方法
        return self.find_local_path(project_name)  # 使用方法1



    def save_to_json(self, data: List[Dict], filename: str) -> None:
        """
        将数据保存为 JSON 文件
        
        :param data: 要保存的数据
        :param filename: 输出文件名
        """
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    def run(self, output_file: str = "mr_results.json"):
        """
        执行完整查询流程
        
        :param output_file: 输出 JSON 文件名
        """
        print(f"查询组 {self.group_path} 中的合并请求...")
        mrs = self.query_mrs(state="opened", labels=["ready_to_sys_staging"])
        filtered_mrs = self.filter_mr_info(mrs)
        print(f"找到 {len(filtered_mrs)} 个符合条件的合并请求")
        self.save_to_json(filtered_mrs, output_file)
        print(f"结果已保存到 {output_file}")
        return filtered_mrs


