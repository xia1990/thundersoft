# 使用快照生成两个版本之间的修改记录
#_*_ coding:utf-8
import xml.etree.ElementTree as ET
import requests
import urllib.parse
from datetime import datetime
import re
import os
from ManifestParser import ManifestParser
from HTMLReportGenerator import HTMLReportGenerator
import argparse
import subprocess
from configparser import ConfigParser
import sys


def get_commits(project, old_rev, new_rev):
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

def get_commits2(project, old_rev, new_rev):
    encoded_project = urllib.parse.quote(project, safe='')
    url = f"{SWF_GITLAB_URL}/api/v4/projects/{encoded_project}/repository/compare"
    params = {"from": old_rev, "to": new_rev}

    try:
        resp = requests.get(url, headers=HEADERS2, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("commits", [])
    except requests.exceptions.RequestException as e:
        return f"API请求失败: {str(e)}"
    except Exception as e:
        return f"处理错误: {str(e)}"


def remove_duplicate_commits(diff_data):
    """
    对diff_data中的commit信息进行去重处理
    基于commit id进行去重，保留第一次出现的commit
    """
    seen_commits = set()
    processed_data = []
    
    for repo_data in diff_data:
        if 'commits' in repo_data and repo_data['commits']:
            unique_commits = []
            for commit in repo_data['commits']:
                commit_id = commit.get('id')
                if commit_id and commit_id not in seen_commits:
                    seen_commits.add(commit_id)
                    unique_commits.append(commit)
                elif not commit_id:
                    # 如果没有id的commit，直接保留
                    unique_commits.append(commit)
            
            # 更新去重后的commits
            repo_data_copy = repo_data.copy()
            repo_data_copy['commits'] = unique_commits
            processed_data.append(repo_data_copy)
        else:
            # 没有commits的数据直接保留
            processed_data.append(repo_data)
    
    return processed_data


def compare_manifests(old_manifests, new_manifests, vcpu_repo, vcpu_source_version, vcpu_target_version):
    if len(old_manifests) != len(new_manifests):
        raise ValueError("old_manifest_list 和 new_manifest_list 长度必须一致！")

    all_results = []
    
    # 处理VCPU的数据
    if vcpu_source_version != vcpu_target_version:
        vcpu_data = {
            'repo_name': vcpu_repo,
            'old_rev': vcpu_source_version,
            'new_rev': vcpu_target_version,
            'from_manifest': "old_file",
            'to_manifest': "new_file"
        }
        vcpu_commits = get_commits2(vcpu_repo, vcpu_source_version, vcpu_target_version)
        if isinstance(vcpu_commits, str):
            vcpu_data['error'] = vcpu_commits
        else:
            vcpu_data['commits'] = vcpu_commits
        all_results.append(vcpu_data)
    else:
        # 处理版本相同的情况
        same_version_data = {
            'repo_name': vcpu_repo,
            'old_rev': vcpu_source_version,
            'new_rev': vcpu_target_version,
            'message': 'Source and target versions are identical',
            'status': 'no_changes'
        }
        all_results.append(same_version_data)
    
    # 处理aosp & qnx 仓库的数据
    for old_file, new_file in zip(old_manifests, new_manifests):
        old_projects = ManifestParser(old_file).get_projects()
        new_projects = ManifestParser(new_file).get_projects()

        for repo_name in old_projects:
            if repo_name in new_projects:
                old_rev = old_projects[repo_name]
                new_rev = new_projects[repo_name]

                if old_rev != new_rev:
                    repo_data = {
                        'repo_name': repo_name,
                        'old_rev': old_rev,
                        'new_rev': new_rev,
                        'from_manifest': old_file,
                        'to_manifest': new_file
                    }

                    commits = get_commits(repo_name, old_rev, new_rev)

                    if isinstance(commits, str):
                        repo_data['error'] = commits
                    else:
                        repo_data['commits'] = commits

                    all_results.append(repo_data)

    # 对所有的commit信息进行去重处理
    all_results = remove_duplicate_commits(all_results)
                    
    return all_results


def shell(command, result=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
    stdout, stderr = process.communicate()
    return_code = process.wait()
    if result:
        # 根据返回码判断命令是否成功执行
        if return_code == 0:
            pass
        else:
            print(command,': 命令执行失败', return_code)

    return return_code, stdout.decode()


# 下载快照文件
def get_xml(artifactory_url, token, source_xml,target_xml):
    down_command = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(source_xml,target_xml,artifactory_url,token)
    status,result = shell(down_command,result=True)  

if __name__ == "__main__":
    config = ConfigParser()
    config.read("/home/gaoyuxia/config.ini")
    GITLAB_BASE_URL = config.get("gitlab", "url")
    GITLAB_TOKEN = config.get("gitlab", "token")
    
    SWF_GITLAB_URL = config.get("gitlab_swf", "url")
    SWF_TOKEN = config.get("gitlab_swf", "token")
    artifactory_url = config.get("artifact", "url")
    artifactory_token = config.get("artifact", "token")

    HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN
    }
    HEADERS2 = {
        "PRIVATE-TOKEN": SWF_TOKEN
    }

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--source_vendor_xml', default='source_vendor_manifest.xml', help='source vendor manifest file')
    parser.add_argument('--source_qssi_xml', default='source_qssi_manifest.xml', help='source qssi manifest file')
    parser.add_argument('--source_qnx_xml', default='source_qnx_manifest.xml', help='source qnx manifest file')
    parser.add_argument('--target_vendor_xml', default='target_vendor_manifest.xml', help='target vendor manifest file')
    parser.add_argument('--target_qssi_xml', default='target_qssi_manifest.xml', help='target qssi manifest file')
    parser.add_argument('--target_qnx_xml', default='target_qnx_manifest.xml', help='target qnx manifest file')
    parser.add_argument('--vcpu_repo', default='apricotqal/civic-vcpu-rsu3.0', help='vcpu repo name')
    parser.add_argument('--vcpu_source_version', default='target_qnx_manifest.xml', help='target qnx manifest file')
    parser.add_argument('--vcpu_target_version', default='target_qnx_manifest.xml', help='target qnx manifest file')

    args = parser.parse_args()
    source_vendor_xml = args.source_vendor_xml
    source_qssi_xml = args.source_qssi_xml
    source_qnx_xml = args.source_qnx_xml
    target_vendor_xml = args.target_vendor_xml
    target_qssi_xml = args.target_qssi_xml
    target_qnx_xml = args.target_qnx_xml
    vcpu_repo = args.vcpu_repo
    vcpu_source_version = args.vcpu_source_version
    vcpu_target_version = args.vcpu_target_version

    # 下载静态manfiest文件
    get_xml(artifactory_url, artifactory_token, source_vendor_xml,"source_vendor_manifest.xml")
    get_xml(artifactory_url, artifactory_token, source_qssi_xml,"source_qssi_manifest.xml")
    get_xml(artifactory_url, artifactory_token, source_qnx_xml,"source_manifest.xml")
    get_xml(artifactory_url, artifactory_token, target_vendor_xml,"target_vendor_manifest.xml")
    get_xml(artifactory_url, artifactory_token, target_qssi_xml,"target_qssi_manifest.xml")
    get_xml(artifactory_url, artifactory_token, target_qnx_xml,"target_manifest.xml")

    old_manifests = ["source_qssi_manifest.xml", "source_vendor_manifest.xml", "source_manifest.xml"]
    new_manifests = ["target_qssi_manifest.xml", "target_vendor_manifest.xml", "target_manifest.xml"]
    
    diff_data = compare_manifests(old_manifests, new_manifests, vcpu_repo, vcpu_source_version, vcpu_target_version)
    
    report_gen = HTMLReportGenerator()
    report_gen.generate(diff_data)