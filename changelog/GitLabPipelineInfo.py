import re
import requests
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import quote

class GitLabPipelineInfo:
    def __init__(self, gitlab_url: str = "https://git.sb.com", private_token: str = None):
        """
        初始化GitLab Pipeline信息获取工具
        
        :param gitlab_url: GitLab基础URL
        :param private_token: GitLab个人访问令牌
        """
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_url = f"{self.gitlab_url}/api/v4"
        self.private_token = private_token
    
    def extract_pipeline_id(self, pipeline_url: str) -> Optional[str]:
        """
        从GitLab Pipeline URL中提取Pipeline ID
        
        :param pipeline_url: GitLab Pipeline的URL
        :return: Pipeline ID字符串，如果提取失败则返回None
        """
        # 方法1：使用正则表达式提取
        pattern = r'/pipelines/(\d+)(?:/|$)'
        match = re.search(pattern, pipeline_url)
        if match:
            return match.group(1)
        
        # 方法2：备用方案，使用字符串分割
        #parts = pipeline_url.split('/')
        #if parts[-1].isdigit():
        #    return parts[-1]
        
        #return None
    
    def get_pipeline_time(self, project_path: str, pipeline_id: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        通过GitLab API获取Pipeline的创建和更新时间
        
        :param project_path: 项目路径，如"mercedes-ci/trigger/rsu-system-staging"
        :param pipeline_id: Pipeline ID
        :return: (创建时间, 更新时间)的元组，如果获取失败则为(None, None)
        """
        if not self.private_token:
            raise ValueError("GitLab private token is required to access the API")
        
        encoded_project = quote(project_path, safe='')
        api_url = f"{self.api_url}/projects/{encoded_project}/pipelines/{pipeline_id}"
        headers = {"PRIVATE-TOKEN": self.private_token}
        
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            pipeline_data = response.json()
            
            created_at = self._parse_datetime(pipeline_data.get('created_at'))
            updated_at = self._parse_datetime(pipeline_data.get('updated_at'))
            
            return created_at, updated_at
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch pipeline info: {e}")
            return None, None
    
    def _parse_datetime(self, time_str: Optional[str]) -> Optional[datetime]:
        """解析GitLab返回的时间字符串"""
        if not time_str:
            return None
        
        try:
            # 处理带时区和不带时区的情况
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
            return None
        except (TypeError, ValueError):
            return None

    def get_pipeline_info(self, pipeline_url: str) -> dict:
        """
        一站式获取Pipeline信息
        
        :param pipeline_url: GitLab Pipeline的完整URL
        :return: 包含提取结果的字典
        """
        # 提取项目路径和Pipeline ID
        pipeline_id = self.extract_pipeline_id(pipeline_url)
        if not pipeline_id:
            return {"error": "Failed to extract pipeline ID from URL"}
        
        # 从URL中提取项目路径
        project_pattern = r'https?://[^/]+/(.+?)/-/pipelines/\d+'
        match = re.match(project_pattern, pipeline_url)
        if not match:
            return {"error": "Failed to extract project path from URL"}
        project_path = match.group(1)
        
        # 获取时间信息
        created_at, updated_at = self.get_pipeline_time(project_path, pipeline_id)
        
        return {
            "pipeline_id": pipeline_id,
            "project_path": project_path,
            "created_at": created_at,
            "updated_at": updated_at,
            "created_at_str": str(created_at) if created_at else None,
            "updated_at_str": str(updated_at) if updated_at else None,
        }


