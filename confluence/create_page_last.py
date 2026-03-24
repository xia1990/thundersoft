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
api_token = ""
space_key = "APRICOT"
parent_page_id = 3407606976

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
    # 写入 txt 文件
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


def create_page():
    result_data = parse_build_paths()
    
    # 第2张表格的内容
    with open("mr_table.html", "r", encoding="utf-8") as f:
      mr_table_html = f.read()

    # 第3张表格的内容
    with open("test_table.html", "r", encoding="utf-8") as f:
      test_table_html = f.read()
    
    # 构建 <tbody> 表格行内容
    table_rows = ""
    # 计算整个表格总共有多少个 <tr> 行数
    total_rows = sum(
        sum(len(kinds) for kinds in builds.values())
        for builds in result_data.values()
    )
    
    first_col_written = False  # 控制是否写入第一列
    for star, builds in result_data.items():
        star_total_rows = sum(len(kinds) for kinds in builds.values())
        star_written = False

        for build_type, kinds in builds.items():
            branches = list(kinds.items())
            build_rowspan = len(branches)

            for idx, (branch, urls) in enumerate(branches):
                archive_urls = "<br>".join([f'<a href="{u}">{u}</a>' for u in urls])
                table_rows += "<tr>\n"

                # 第一列：仅在第一次写入，并合并所有行
                if not first_col_written:
                    table_rows += f'  <td rowspan="{total_rows}">8295_master</td>\n'
                    first_col_written = True

                # VERSION 列
                if not star_written:
                    table_rows += f'  <td rowspan="{star_total_rows}">{star}</td>\n'
                    star_written = True

                # BUILD TYPE 列
                if idx == 0:
                    table_rows += f'  <td rowspan="{build_rowspan}">{build_type}</td>\n'

                # 其余列
                table_rows += f"  <td>{branch}</td>\n"
                table_rows += f"  <td>{archive_urls}</td>\n"
                table_rows += f"  <td></td>\n"
                table_rows += f"  <td></td>\n"
                table_rows += "</tr>\n"
    
    # 构建 HTML 表格内容
    page_content = f"""
    <h4>构建日期: {BUILD_DATE}</h4>
    <h4>@Integration</h4>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>VARSION</th>
            <th>ELECTROMECHAINCAL ARCHIECTURE</th>
            <th>BUILD TYPE</th>
            <th>PACKAGE TYPE</th>
            <th>ARCHIVE URL</th>
            <th>DECISION</th>
            <th>REASON FOR EXTENDING</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>

    <h1 data-nh-numbering="" talk-marker="43" talk-page-id="3221943987" talk-page-version="5" id="Example-MRs:">MRs:</h1>
    <p talk-marker="44" talk-page-id="3221943987" talk-page-version="5"><a class="confluence-userlink user-mention userlink-1" data-username="ljinrui" href="/display/~ljinrui" data-linked-resource-id="3010866811" data-linked-resource-version="1" data-linked-resource-type="userinfo" data-base-url="https://wiki.sb.com" title="" data-user-hover-bound="true">li jinrui</a> &nbsp;@integration</p>
    {mr_table_html}
    <h1 data-nh-numbering="" talk-marker="54" talk-page-id="3407581415" talk-page-version="5" id="Example-Testresults:">Test results:</h1>
    <p talk-marker="55" talk-page-id="3407581415" talk-page-version="5"><strong style="letter-spacing: 0.0px;">Test Summary</strong></p>
    {test_table_html}
    
    """

    # Confluence API 请求
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    page_data = {
        "type": "page",
        "title": ESTAND,
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
        print("\033[1;31m 参数一：sb/sb/sb/20250722/E233.0/ & pipeline_url \033[0m") 
        print("\033[1;31m 参数二：pipeline_url \033[0m")  
        print("\033[1;31m 参数三：ESTAND \033[0m") 
        sys.exit(1)  # 非零退出码表示错误

    # 加载环境变量
    config = ConfigParser()
    config.read("/home/gaoyuxia/config.ini")
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

    # now = datetime.now()
    # build_date = now.strftime("%Y-%m-%d %H:%M:%S")
    
    client = GitlabPipelineClient(pipeline_url=pipeline_url, private_token=PRIVATE_TOKEN)
    BUILD_DATE = client.get_pipeline_date()
    create_page()

