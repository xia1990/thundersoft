from configparser import ConfigParser
import subprocess
from pathlib import Path
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import requests
import os
import sys
import glob
from GitlabPipelineClient import GitlabPipelineClient
from urllib.parse import urljoin


confluence_url = "https://wiki.sb.com"
url = f"{confluence_url}/rest/api/content"
artifactory_url = "https://artifact.sb.com:443/artifactory/"

username = "GAYUXIA"
api_token = "token"
space_key = "APRICOT"
parent_page_id = 1234567890

# step 查询版本信息，存入version.txt
def query_artifactory(ARTIFACTORY_URL,ARTIFACTORY_TOKEN,SEARCH_PATH):
  """查询Artifactory并保存结果到path.txt"""
  cmd = [
    "jf", "rt", "search",
    SEARCH_PATH,
    "--url", ARTIFACTORY_URL,
    "--user", "GAYUXIA",
    "--password", ARTIFACTORY_TOKEN,
    "--insecure-tls=false",
    "--recursive"
  ]
    
  try:
    print("正在查询Artifactory...")
    result = subprocess.run(
      cmd,
      check=True,
      text=True,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE
    )
    Path("version.txt").write_text(result.stdout, encoding="utf-8")
    print("查询结果已保存到 version.txt")
    return True
  except subprocess.CalledProcessError as e:
    print(f"查询失败: {e.stderr}")
    raise


def parse_build_paths():
    # 读取数据（从 version.txt）
    with open("version.txt", "r") as f:
        data = json.load(f)

    # 初始化结果结构：{ STAR version → build_type → category → set() }
    # 这里的结构就是：{ STAR 3.0 -> dev_userdebug -> flat_build/swup > 去重}
    result = defaultdict(lambda: defaultdict(lambda: {"flat_build": set(), "swup": set()}))

    def classify_path(path):
        # 分类类别：flat_build 或 swup
        if "flat_build" in path and path.endswith(".tar.gz"):
            category = "flat_build"
        elif "swup" in path:
            category = "swup"
        else:
            return None, None, None

        # 构建类型分类
        if "dev_userdebug" in path or "userdebug" in path:
            build_type = "dev_userdebug"
        elif "dev" in path or "dev_user" in path:
            build_type = "dev_user"
        elif "prod-pl_user" in path or "prod-pl" in path:
            build_type = "prod-pl_user"
        elif "prod-rl_user" in path or "prod-rl" in path:
            build_type = "prod-rl_user"
        else:
            return None, None, None

        # 提取 STAR 版本（如 STAR3.0 或 STAR3.5）
        if "STAR3.0" in path:
            star_version = "STAR3.0"
        elif "STAR3.5" in path:
            star_version = "STAR3.5"
        else:
            return None, None, None

        return star_version, build_type, category

    # 遍历并分类
    for entry in data:
        path = entry.get("path", "")
        star_version, build_type, category = classify_path(path)
        if star_version and build_type and category:
            if category == "swup":
                path = "/".join(path.split("/")[:12])  # 裁剪 swup 路径
            result[star_version][build_type][category].add(path)

    # 转换为 JSON 可序列化结构（set → list）
    clean_result = {
        star: {
            build: {
                kind: sorted([f"https://artifact.sb.com/artifactory/{p}" for p in paths])
                for kind, paths in builds.items()
            }
            for build, builds in star_data.items()
        }
        for star, star_data in result.items()
    }

    # 写入结果
    with open("classified_builds_by_star.json", "w") as f:
        json.dump(clean_result, f, indent=2)

    print("分类结果已写入 classified_builds_by_star.json")
    #写入 txt 文件
    with open("output.txt", "w", encoding="utf-8") as file:
        print_nested_to_file(clean_result, file)

    print("已成功导出到 output.txt")
    
    return clean_result
    

# 导出为纯文本 txt
def print_nested_to_file(data, file, indent=0):
    prefix = "    " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            file.write(f"{prefix}{key}\n") # 打印当前键（带缩进）
            print_nested_to_file(value, file, indent + 1) # 递归处理值（缩进+1）
    elif isinstance(data, list):
        for item in data:
            print_nested_to_file(item, file, indent) # 递归处理列表项（保持缩进）
    else:
        file.write(f"{prefix}{data}\n")


def create_page(ESTAND,BUILD_DATE):
    result_data = parse_build_paths()

    for i,data in result_data.items():
        if i == "STAR3.0":
            dev_userdebug = data.get("dev_userdebug")
            dev_user = data.get("dev_user")
            pl_user = data.get("prod-pl_user")
            rl_user = data.get("prod-rl_user")
        elif i == "STAR3.5":
            dev_userdebug2 = data.get("dev_userdebug")
            rl_user2 = data.get("prod-rl_user")
        else:
            pass
        # print(data)

    # 第2张表格的内容
    with open("main.html", "r", encoding="utf-8") as f:
      main_html = f.read()

    # 替换标记位置（假设原文件中有 <!-- INSERT_HERE -->）
    modified_html = main_html.replace("<!-- BUILD_DATE -->", BUILD_DATE) \
                         .replace("<!-- BUILD_VERSION -->", ESTAND) \
                         .replace("<!-- dev_userdebug_url -->", str(dev_userdebug)) \
                         .replace("<!-- dev_user_url -->",str(dev_user)) \
                         .replace("<!-- pl_user_url -->",str(pl_user)) \
                         .replace("<!-- rl_user_url -->",str(rl_user)) \
                         .replace("<!-- dev_userdebug_url_2 -->",str(dev_userdebug2)) \
                         .replace("<!-- rl_user_url_2 -->",str(rl_user2)) 

    # 构建 HTML 表格内容
    page_content = f"""
    {modified_html}
    """

    # Confluence API 请求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }

    page_data = {
        "type": "page",
        "title": "E241+Sys+MR+Q-Gate",
        "ancestors": [{"id": parent_page_id}],
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": page_content,
                "representation": "storage"
            }
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(page_data))
    if response.status_code in [200, 201]:
        page_info = response.json()
        base_url = "https://wiki.sb.com/"
        webui_path = page_info.get("_links", {}).get("webui", "")
        page_url = urljoin(base_url, webui_path.lstrip("/"))
        print(f"页面创建成功！访问链接: {page_url}")
    else:
        print(f"页面创建失败: {response.status_code}")
        print(response.text)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("\033[1;31m 需要输入3个参数 \033[0m") 
        print("\033[1;31m 参数一：a/b/c/20250722/E233.0/ & pipeline_url \033[0m") 
        print("\033[1;31m 参数二：pipeline_url \033[0m")  
        print("\033[1;31m 参数三：ESTAND \033[0m") 
        sys.exit(1)  # 非零退出码表示错误

    # 加载环境变量
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")
    PRIVATE_TOKEN = config.get("gitlab","token")
    GITLAB_URL = config.get("gitlab","url")
    ARTIFACTORY_URL = config.get("artifact","url")
    ARTIFACTORY_TOKEN = config.get("artifact","token")
    # 删除 *.txt 文件
    for file_path in glob.glob("*.txt"):
        os.remove(file_path)
        print(f"已删除 *.txt 文件: {file_path}")

    SEARCH_PATH = sys.argv[1]
    pipeline_url = sys.argv[2]
    ESTAND = sys.argv[3]
    query_artifactory(ARTIFACTORY_URL,ARTIFACTORY_TOKEN,SEARCH_PATH)
    parse_build_paths()
    
    client = GitlabPipelineClient(pipeline_url=pipeline_url, private_token=PRIVATE_TOKEN)
    BUILD_DATE = client.get_pipeline_date()
    create_page(ESTAND,BUILD_DATE)

