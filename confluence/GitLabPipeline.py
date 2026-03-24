import requests
from datetime import datetime
from urllib.parse import urlparse, unquote
import re

class GitLabPipeline:
    def __init__(self, gitlab_url: str, private_token: str):
        self.gitlab_url = gitlab_url.rstrip("/")
        self.headers = {"PRIVATE-TOKEN": private_token}

    def get_date_from_pipeline_url(self, pipeline_url: str) -> str:
        project_path, pipeline_id = self._parse_pipeline_url(pipeline_url)
        project_id = self._get_project_id(project_path)
        created_at = self._get_pipeline_created_at(project_id, pipeline_id)
        return self._format_date(created_at)

    def _parse_pipeline_url(self, url: str):
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")

        try:
            pipeline_index = path_parts.index("pipelines")
            pipeline_id = int(path_parts[pipeline_index + 1])
            # 获取项目路径（即 pipelines 之前的部分，去除 -）
            project_parts = []
            for part in path_parts[:pipeline_index]:
                if part != "-":
                    project_parts.append(part)
            project_path = "/".join(project_parts)
            return project_path, pipeline_id
        except (ValueError, IndexError):
            raise ValueError("无法解析项目路径或 pipeline ID")

    def _get_project_id(self, project_path: str) -> int:
        # safer to URL-encode project path
        encoded_path = requests.utils.quote(project_path, safe='')
        url = f"{self.gitlab_url}/api/v4/projects/{encoded_path}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()["id"]

    def _get_pipeline_created_at(self, project_id: int, pipeline_id: int) -> str:
        url = f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()["created_at"]

    def _format_date(self, iso_string: str) -> str:
        dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt.strftime("%Y-%m-%d ")
