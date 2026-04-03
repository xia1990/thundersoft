import subprocess
import json
import pandas as pd
from datetime import datetime
import re
from pathlib import Path
import os

def configure_artifactory():
    """配置Artifactory服务器连接"""
    # 检查是否已配置
    check_cmd = ["jf", "c", "show", "artifactory"]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Artifactory配置已存在")
        return True
    
    # 配置Artifactory服务器
    config_cmd = [
        "jf", "c", "add", "artifactory",
        "--url=https://artifact.sb.com/artifactory/",
        "--user=GAYUXIA",  # 替换为实际用户名
        "--password=token",  # 替换为实际密码或使用访问令牌
        "--interactive=false"
    ]
    
    try:
        result = subprocess.run(config_cmd, check=True, capture_output=True, text=True)
        print("Artifactory配置成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Artifactory配置失败: {e.stderr}")
        return False

def configure_artifactory_with_token():
    """使用访问令牌配置Artifactory服务器"""
    # 检查是否已配置
    check_cmd = ["jf", "c", "show", "artifactory"]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Artifactory配置已存在")
        return True
    
    # 使用访问令牌配置
    config_cmd = [
        "jf", "c", "add", "artifactory",
        "--url=https://artifact.sb.com/artifactory/",
        "--access-token=token",  # 替换为实际访问令牌
        "--interactive=false"
    ]
    
    try:
        result = subprocess.run(config_cmd, check=True, capture_output=True, text=True)
        print("Artifactory配置成功（使用访问令牌）")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Artifactory配置失败: {e.stderr}")
        return False

def check_jfrog_cli_installed():
    """检查JFrog CLI是否已安装"""
    try:
        result = subprocess.run(["jf", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"JFrog CLI已安装: {result.stdout.strip()}")
            return True
        else:
            print("JFrog CLI未正确安装")
            return False
    except FileNotFoundError:
        print("JFrog CLI未安装，请先安装JFrog CLI")
        return False

def create_spec_file():
    spec = {
        "files": [
            {
                "pattern": "sb/sb/RSE_System_Staging_Build/*/*",
                "recursive": "true",              
                "includeDirs": "false",           
                "sortBy": ["created"],
                "sortOrder": "asc"
            }
        ]
    }
    with open("search-spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print("创建 search-spec.json")

def run_jfrog_search():
    cmd = [
        "jf", "rt", "search",
        "--spec=search-spec.json",
        "--server-id=artifactory"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        with open("result.json", "w") as f:
            f.write(result.stdout)
        print("结果已保存到 result.json")
        return True
    except subprocess.CalledProcessError as e:
        print(f"执行失败:\n{e.stderr}")
        return False

def get_data(filename="result.json"):
    prefix = "sb/sb/RSE_System_Staging_Build/"
    cutoff_date = datetime.strptime("2025-04-14", "%Y-%m-%d")

    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    filtered_data = []
    for item in data:
        created_str = item.get("created", "")[:10]  # 只取日期部分
        try:
            created_date = datetime.strptime(created_str, "%Y-%m-%d")
        except ValueError:
            # 无效日期格式跳过这条
            continue

        if created_date >= cutoff_date:
            path = item.get("path", "")
            if path.startswith(prefix):
                path = path[len(prefix):]
            if (
                path.endswith(('.tar', '.tar.gz')) and
                (
                    # 匹配 swup/dev/*/*/BOOT/
                     ('swup/dev' in path and '/BOOT/' in path and 'BOOT_ALWAYS_ON' not in path) or
                    # 匹配 flat_build/dev/
                    ('flat_build/dev' in path) or
                    # 匹配 fastboot_build/dev/
                    #('fastboot_build/dev/' in path) or
                    ('android/dev/' in path)
                )
            ):
                path_obj = Path(path)
                size_bytes = item.get("size")
                size_gb = round(size_bytes / (1024**3), 2) if size_bytes is not None else None

                package_name = os.path.basename(path)
                parts = path.split('/')
                version = parts[1] if len(parts) > 1 else ""
                if not package_name.startswith("symbols_vmlinux"):
                    filtered_data.append({
                        "created": created_str,
                        "version": version,
                        "path": path,
                        "package_name" : package_name,
                        "size": size_gb
                    })

    df = pd.DataFrame(filtered_data)
    df.to_excel('output.xlsx', index=False)

if __name__ == "__main__":
    # 检查JFrog CLI是否安装
    if not check_jfrog_cli_installed():
        exit(1)

    if not configure_artifactory_with_token():
        print("请手动配置Artifactory访问令牌")
        print("运行: jf c add artifactory --url=https://artifact.sb.com/artifactory/ --access-token=token")
        exit(1)
    
    # 继续执行原有流程
    create_spec_file()
    if run_jfrog_search():
        get_data(filename="result.json")