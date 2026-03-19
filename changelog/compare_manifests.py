import xml.etree.ElementTree as ET
import requests
import urllib.parse
from datetime import datetime
import re
import pdfkit
import os

GITLAB_BASE_URL = "https://git.sb.com"
GITLAB_TOKEN = "token"

HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN
}

def generate_html_report(old_manifests, new_manifests, output_file="commit_report.html"):
    """生成包含提交记录的HTML报告"""
    # 1. 获取差异数据
    diff_data = compare_manifests(old_manifests, new_manifests, html_mode=True)
    
    # 2. 生成HTML内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>General Changes</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            .timestamp {{ color: #666; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #f8f9fa; position: sticky; top: 0; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .repo-header {{ background-color: #e7f5ff !important; font-weight: bold; }}
            .commit-id {{ font-family: monospace; }}
            .error {{ color: #dc3545; }}
        </style>
    </head>
    <body>
        <h1>General Changes</h1>
        <div class="timestamp">Changes of subsystem in GitLab: android, qnx, VCPU</div>
        <table>
            <thead>
                <tr>
                    <th width="15%">Commit</th>
                    <th width="15%">Author</th>
                    <th width="55%">Message</th>
                    <th width="15%">Jira-ID</th>
                </tr>
            </thead>
            <tbody>
    """

    # 3. 填充表格内容
    for repo_data in diff_data:
        html_content += f"""
            <tr class="repo-header">
                <td colspan="4">
                    {repo_data['repo_name']} | 
                    version: {repo_data['old_rev'][:8]}..{repo_data['new_rev'][:8]}
                </td>
            </tr>
        """
        
        if 'error' in repo_data:
            html_content += f"""
            <tr>
                <td colspan="4" class="error"> {repo_data['error']}</td>
            </tr>
            """
        else:
            for commit in repo_data['commits']:
                d = commit.get("message")
                jira_id = 'N/A'  
                if d.startswith('APRICOT') or "APRICOT" in d:
                    list_jira = re.findall(r'(APRICOT.*?\d+)', d)
                    jira_id = list_jira[0] if list_jira else 'No Jira-ID Found'

                html_content += f"""
                <tr>
                    <td class="commit-id">
                        <a href="{GITLAB_BASE_URL}/{repo_data['repo_name']}/-/commit/{commit['id']}" 
                           target="_blank" title="View commit">
                            {commit['short_id']}
                        </a>
                    </td>
                    <td>{commit['author_name']}</td>
                    <td>{commit['title']}</td>
                    <!--<td>{repo_data['repo_name'].split('/')[-1]}</td>-->
                    <td>{jira_id}</td>
                </tr>
                """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    # 4. 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"报告已生成：{output_file}")
    html_to_pdf(output_file, "commit_report.pdf")


def html_to_pdf(html_file_path, output_pdf_path):
    """
    使用 pdfkit 将本地 HTML 文件转换为 PDF。
    """
    try:
        pdfkit.from_file(html_file_path, output_pdf_path)
        print(f"PDF 已生成：{output_pdf_path}")
    except Exception as e:
        print(f"PDF 转换失败: {e}")


def parse_manifest(path):
    """解析manifest.xml文件"""
    tree = ET.parse(path)
    root = tree.getroot()

    remotes = {}
    for remote in root.findall('remote'):
        fetch_raw = remote.get("fetch", "")
        fetch = fetch_raw.replace("https://git.sb.com/", "")

    projects = {}
    for project in root.findall("project"):
        repo_name = project.get("name")
        revision = project.get("revision")
        if fetch == "RSE/android/AOSP":
            repo_url = os.path.join(fetch,repo_name)
            projects[repo_url] = revision
        else:
            # QNX 侧仓库
            print("qnx侧仓库：",repo_name)
            projects[repo_name] = revision

    return projects


def get_commits(project, old_rev, new_rev):
    """通过GitLab API获取提交记录"""
    encoded_project = urllib.parse.quote(project, safe='')
    url = f"{GITLAB_BASE_URL}/api/v4/projects/{encoded_project}/repository/compare"
    params = {"from": old_rev, "to": new_rev}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("commits", [])
    except requests.exceptions.RequestException as e:
        return f"API请求失败: {str(e)}"
    except Exception as e:
        return f"处理错误: {str(e)}"


def compare_manifests(old_manifest_list, new_manifest_list, html_mode=False):
    """
    比较多个 manifest 对的差异。
    :param old_manifest_list: List[str]，旧版本 manifest 文件路径
    :param new_manifest_list: List[str]，新版本 manifest 文件路径
    :return: List[dict]，每个项目变更的提交记录
    """
    if len(old_manifest_list) != len(new_manifest_list):
        raise ValueError("old_manifest_list 和 new_manifest_list 长度必须一致！")

    all_results = []

    for i in range(len(old_manifest_list)):
        old_manifest = old_manifest_list[i]
        new_manifest = new_manifest_list[i]

        old_projects = parse_manifest(old_manifest)
        new_projects = parse_manifest(new_manifest)
        print(old_projects,new_projects)

        for repo_name in old_projects:
            if repo_name in new_projects:
                old_rev = old_projects[repo_name]
                new_rev = new_projects[repo_name]

                if old_rev != new_rev:
                    repo_data = {
                        'repo_name': repo_name,
                        'old_rev': old_rev,
                        'new_rev': new_rev,
                        'from_manifest': old_manifest,
                        'to_manifest': new_manifest
                    }

                    commits = get_commits(repo_name, old_rev, new_rev)

                    if isinstance(commits, str):
                        repo_data['error'] = commits
                    else:
                        repo_data['commits'] = commits

                    all_results.append(repo_data)

    return all_results

if __name__ == "__main__":
    print("需要将原xml与现在的xml下载到本地")
    old_manifests = ["source_qssi_manifest.xml","source_vendor_manifest.xml","source_manifest.xml"]
    new_manifests = ["target_qssi_manifest.xml","target_vendor_manifest.xml","target_manifest.xml"]
    generate_html_report(old_manifests,new_manifests)