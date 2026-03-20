import requests
import urllib.parse
import sys

class Query:
    def __init__(self, base_url, group_name, private_token):
        self.base_url = base_url.rstrip("/")
        self.group_name = group_name
        self.headers = {
            "PRIVATE-TOKEN": private_token
        }

    def get_group_id(self):
        url = f"{self.base_url}/api/v4/groups/{self.group_name}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        group = response.json()
        return group.get("id")  


    def get_open_mrs_by_label(self, label):
        group_id = self.get_group_id()
        url = f"{self.base_url}/api/v4/groups/{group_id}/merge_requests"
        
        params = {
            "state": "opened",
            "labels": label,
            "with_labels_details": True,
            "per_page": 100  # 拉取更多（默认20），可配合分页
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        mrs = response.json()

        result = []
        for mr in mrs:
            result.append({
                "project": mr['references']['full'].split('!')[0],  # 提取项目路径
                "title": mr['title'],
                "author": mr['author']['name'],
                "web_url": mr['web_url'],
                "mr_iid": mr['iid'],
                "project_id": mr['project_id'],
            })

        return result

