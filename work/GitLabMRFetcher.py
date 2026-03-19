import requests
import json
from collections import defaultdict
import re

class GitLabMRFetcher:
    def __init__(self, gitlab_url, group_path, private_token):
        self.gitlab_url = gitlab_url
        self.group_path = group_path
        self.private_token = private_token

    def _get_headers(self):
        return {
            "PRIVATE-TOKEN": self.private_token
        }

    def _fetch_merge_requests(self, params):
        all_mrs = []
        page = 1
        per_page = 100

        while True:
            params.update({
                "page": page,
                "per_page": per_page,
            })
            url = f"{self.gitlab_url}/groups/{self.group_path}/merge_requests"
            response = requests.get(url, params=params, headers=self._get_headers())

            if response.status_code != 200:
                print(f"请求失败，状态码: {response.status_code}")
                print(response.text)
                break
                
            mrs = response.json()
            if not mrs:
                break

            all_mrs.extend(mrs)
            page += 1

            if 'next' not in response.links:
                break

        return all_mrs

    def _request_merge_requests(self, label=None, page=1, per_page=100):
        url = f"{self.gitlab_url}/api/v4/groups/{self.group_path}/merge_requests"
        headers = {"Private-Token": self.private_token}
        params = {
            "state": "opened",
            "scope": "all",
            "page": page,
            "per_page": per_page,
        }
        if label:
            params["labels"] = label

        response = requests.get(url, headers=headers, params=params)
        return response


    # 提取分页请求逻辑，统一请求处理
    def get_filtered_domain_labels(self):
        params = {
            "state": "opened",
            "scope": "all",
            "labels": "domain::*,ready_to_review"
        }

        mrs = self._fetch_merge_requests(params)
        filtered_labels = []

        for mr in mrs:
            domain_labels = [label for label in mr.get('labels', []) if label.startswith('domain::')]
            for label in domain_labels:
                son_label = label.replace('domain::', '')
                filtered_labels.append(son_label)

        return filtered_labels


    def get_open_mrs(self):
        params = {
            "state": "opened",
            "scope": "all",
            "target_branch": "8295_master"
        }
        mrs = self._fetch_merge_requests(params)
        
        # 按项目分组并整理数据
        projects_dict = {}
        for mr in mrs:
            project_id = mr.get("project_id")
            repo_url = re.sub(r"/-/merge_requests/\d+", "", mr.get('web_url'))
            
            # 如果项目不在字典中，初始化一个空列表
            if repo_url not in projects_dict:
                projects_dict[repo_url] = []
                
            # 提取需要的字段
            mr_info = {
                "iid": mr.get("iid"),
                "project_id": project_id,
                "web_url": mr.get("web_url"),
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "author": mr.get("author", {}).get("username")
                # 可以添加其他需要的字段
                # "title": mr.get("title"),
                # "author": mr.get("author", {}).get("name"),
            }
            
            projects_dict[repo_url].append(mr_info)
        
        # 对每个项目的MR按iid升序排序
        for project_id in projects_dict:
            projects_dict[project_id].sort(key=lambda x: x["iid"])
        
        # 写入文件
        with open("open_mr.json", "w", encoding="utf-8") as json_file:
            json.dump(projects_dict, json_file, ensure_ascii=False, indent=4)
        
        return projects_dict


    def get_filtered_son_mrs(self, son_label):
        params = {
            "state": "opened",
            "scope": "all",
            "labels": son_label
        }

        mrs = self._fetch_merge_requests(params)
        filtered_mrs_by_project = defaultdict(list)

        for mr in mrs:
            if mr.get('target_branch') != "8295_master":
                print('-' * 100)
                print(mr.get('web_url'))
                print('-' * 100)
                continue

            filtered_mr = {
                "project_id": mr.get("project_id"),
                "iid": mr.get("iid"),
                "source_branch": mr.get("source_branch"),
                "target_branch": mr.get("target_branch"),
                "web_url": mr.get("web_url"),
                "author": mr.get("author", {}).get("username"),
                "sha": mr.get("sha"),
                "labels": mr.get("labels", [])
            }

            filtered_mrs_by_project[mr.get("project_id")].append(filtered_mr)

        # 对每个 project_id 下的 MRs 按 iid 排序
        sorted_filtered_mrs = []
        for project_id in filtered_mrs_by_project:
            sorted_mrs = sorted(filtered_mrs_by_project[project_id], key=lambda x: x['iid'])
            sorted_filtered_mrs.extend(sorted_mrs)

        return sorted_filtered_mrs


    def fetch_mrs_with_label(self, label):
        filtered_mrs = []
        page = 1

        while True:
            response = self._request_merge_requests(label=label, page=page)
            # 输出调试信息
            #print(f"[调试] 请求 URL: {response.url}")
            #print(f"[调试] 状态码: {response.status_code}")
            #print(f"[调试] 响应内容: {response.text[:200]}")  # 只打印前200字符，防止太长
            if response.status_code != 200:
                print(f"请求失败，状态码: {response.status_code}")
                print(response.text)
                break

            mrs = response.json()
            if not mrs:
                break

            filtered_mrs.extend(mrs)
            if 'next' not in response.links:
                break
            page += 1

        return filtered_mrs

    def save_mrs_to_file(self, mrs_list, file_name="mrs_ready_to_staging.json"):
        with open(file_name, "w", encoding="utf-8") as json_file:
            json.dump(mrs_list, json_file, ensure_ascii=False, indent=4)
        print(f"数据已保存，数量: {len(mrs_list)}，文件: {file_name}")

