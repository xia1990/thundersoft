import requests
from datetime import datetime
from urllib.parse import urlparse, unquote


class GitlabPipelineClient:
    def __init__(self, pipeline_url: str, private_token: str):
        """
        GitLab 客户端：自动解析 pipeline_url，简化调用

        :param pipeline_url: 完整的 pipeline 页面 URL，例如：
                             https://git.abc.com/group/project/-/pipelines/123456
        :param private_token: GitLab 私有令牌（需要 read_api 权限）
        """
        self.pipeline_url = pipeline_url
        self.private_token = private_token
        self.headers = {"PRIVATE-TOKEN": private_token}

        # 解析 URL
        self.base_url, self.project_path, self.pipeline_id = self._parse_pipeline_url(pipeline_url)

    def _parse_pipeline_url(self, url: str):
        """
        解析 pipeline URL，提取 base_url、project_path 和 pipeline_id
        """
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")

        if "-/pipelines" not in url:
            raise ValueError("URL 不是合法的 GitLab pipeline 链接")

        try:
            # 提取 pipeline_id（最后一个部分）
            pipeline_id = int(path_parts[-1])
            # 提取项目路径（去掉最后的 ['-', 'pipelines', '{id}'] 三段）
            project_path_parts = path_parts[:-3]
            project_path = "/".join(project_path_parts)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            raise ValueError("无法解析 pipeline URL")

        return base_url, unquote(project_path), pipeline_id

    def _get(self, endpoint: str) -> dict:
        """
        发送 GET 请求
        """
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"请求失败: {response.status_code}\n{response.text}")

    def get_pipeline_info(self) -> dict:
        """
        获取 pipeline 的详细信息
        """
        from urllib.parse import quote
        encoded_project = quote(self.project_path, safe="")
        endpoint = f"/api/v4/projects/{encoded_project}/pipelines/{self.pipeline_id}"
        return self._get(endpoint)

    def get_pipeline_date(self) -> str:
        """
        获取 pipeline 的构建日期（如 "2025-07-24"）
        """
        info = self.get_pipeline_info()
        created_at = info.get("created_at")
        if not created_at:
            raise ValueError("pipeline 中没有 created_at 字段")
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.date().isoformat()
