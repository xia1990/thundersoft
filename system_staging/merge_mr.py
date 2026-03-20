# -*- coding: utf-8 -*-

import os
import sys
import requests
import json
from configparser import ConfigParser
import argparse
import subprocess
import urllib.parse
import glob


def run_cmd(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return result


def batch_merge_mrs(project_id, mr_iid_list, merge_params=None):
    """
    批量合并 Merge Requests

    :param project_id: 项目ID（数字或 URL编码路径，如 'namespace%2Fproject' 或 'namespace/project'）
    :param mr_iid_list: 要合并的MR IID列表，如 [101, 102] 或 单个 101
    :param merge_params: 合并参数（可选），如 {'squash': True}
    :return: 合并结果列表
    """
    if not PRIVATE_TOKEN:
        raise ValueError("未配置 PRIVATE_TOKEN")

    if merge_params is None:
        merge_params = {}

    results = []
    success_count = 0

    # 确保 mr_iid_list 为列表
    if not isinstance(mr_iid_list, (list, tuple)):
        mr_iid_list = [mr_iid_list]

    # 尝试把 id 转为 int 以便正确排序（否则按字符串）
    def _try_int(x):
        try:
            return int(x)
        except Exception:
            return x

    try:
        sorted_list = sorted(mr_iid_list, key=lambda x: _try_int(x))
    except Exception:
        sorted_list = mr_iid_list

    # 对 project_id 做 URL 编码（但保留纯数字 id 不编码）
    project_id_str = str(project_id)
    if project_id_str.isdigit():
        project_encoded = project_id_str
    else:
        project_encoded = urllib.parse.quote_plus(project_id_str)

    for mr_iid in sorted_list:
        try:
            # 1. 检查MR状态
            mr_info = get_mr_info(project_encoded, mr_iid)

            # 如果已经 merged，跳过并记录
            if mr_info.get('state') == "merged":
                results.append({
                    'mr_iid': mr_iid,
                    'status': 'skipped',
                    'reason': 'already merged',
                    'web_url': mr_info.get('web_url')
                })
                continue

            # 检查 merge_status
            if mr_info.get('merge_status') != 'can_be_merged':
                results.append({
                    'mr_iid': mr_iid,
                    'status': 'skipped',
                    'reason': f"MR状态不可合并: {mr_info.get('merge_status')}",
                    'web_url': mr_info.get('web_url')
                })
                continue

            # 2. 执行合并
            merge_url = f"{GITLAB_URL.rstrip('/')}/api/v4/projects/{project_encoded}/merge_requests/{mr_iid}/merge"
            response = requests.put(
                merge_url,
                headers={"PRIVATE-TOKEN": PRIVATE_TOKEN},
                params=merge_params,
                timeout=15
            )

            # 合并成功可能返回 200 或 201
            if response.status_code in (200, 201):
                success_count += 1
                results.append({
                    'mr_iid': mr_iid,
                    'status': 'merged',
                    'web_url': mr_info.get('web_url')
                })
            else:
                # 尝试安全解析返回的消息
                reason = ""
                try:
                    reason = response.json().get('message', '') or response.json()
                except Exception:
                    reason = response.text
                results.append({
                    'mr_iid': mr_iid,
                    'status': 'failed',
                    'reason': f"HTTP {response.status_code}: {reason}",
                    'web_url': mr_info.get('web_url')
                })

        except requests.HTTPError as he:
            results.append({
                'mr_iid': mr_iid,
                'status': 'error',
                'reason': f"HTTPError: {str(he)}"
            })
        except Exception as e:
            results.append({
                'mr_iid': mr_iid,
                'status': 'error',
                'reason': str(e)
            })

    # summary 打印（可选）
    if results:
        merged = [r for r in results if r['status'] == 'merged']
        failed = [r for r in results if r['status'] in ('failed', 'error')]
        skipped = [r for r in results if r['status'] == 'skipped']
        print(f"[batch_merge_mrs] project={project_id_str} merged={len(merged)} failed={len(failed)} skipped={len(skipped)}")

    return results


def get_mr_info(project_id_encoded, mr_iid):
    """获取MR详细信息。传入的 project_id 已经是编码后的（或纯数字）"""
    url = f'{GITLAB_URL.rstrip("/")}/api/v4/projects/{project_id_encoded}/merge_requests/{mr_iid}'
    response = requests.get(
        url,
        headers={"PRIVATE-TOKEN": PRIVATE_TOKEN},
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def load_mr_list_from_file(filename):
    """
    从 JSON 文件加载 MR 列表并调用 batch_merge_mrs 执行合并。
    支持文件内容为 list[ { "project_id": "...", "mr_iid": [1,2] }, ... ]
    """
    if not os.path.exists(filename):
        print(f"[load_mr_list_from_file] 文件不存在: {filename}")
        return []

    try:
        with open(filename, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[load_mr_list_from_file] JSON 解析失败 {filename}: {e}")
        return []
    except Exception as e:
        print(f"[load_mr_list_from_file] 无法读取文件 {filename}: {e}")
        return []

    if not data:
        print(f"[load_mr_list_from_file] 文件为空或包含 null: {filename}")
        return []

    all_results = []

    # 支持 data 为 dict 或 list
    items = data if isinstance(data, list) else [data]

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            print(f"[load_mr_list_from_file] 跳过非 dict 项: index={idx}")
            continue

        project_id = item.get("project_id") or item.get("project") or item.get("projectId")
        mr_list = item.get("mr_iid") or item.get("mr_iids") or item.get("mrs") or item.get("mr")

        if project_id is None or mr_list is None:
            print(f"[load_mr_list_from_file] 缺少 project_id 或 mr_iid: index={idx} content={item}")
            continue

        print(f"[load_mr_list_from_file] 处理 project={project_id} mrs={mr_list}")
        merge_results = batch_merge_mrs(project_id, mr_list)
        all_results.extend(merge_results)

        # 打印失败的 MR（方便查看）
        for result in merge_results:
            if result.get('status') == "failed":
                print(f"失败的MR !{result.get('web_url', '')} : {result.get('reason')}")
    return all_results


if __name__ == "__main__":
    config = ConfigParser()
    config.read("/home/gayuxia/config.ini")

    # 读取配置，存在异常会抛出，确保 config 文件正确
    try:
        token = config.get("artifact", "token")
        artifactory_url = config.get('artifact', 'url')
    except Exception:
        token = None
        artifactory_url = None

    try:
        PRIVATE_TOKEN = config.get("gitlab", "token")
        GITLAB_URL = config.get('gitlab', 'url')
    except Exception as e:
        print(f"[main] 读取 gitlab 配置失败: {e}")
        sys.exit(1)

    # 创建 ArgumentParser 对象
    parser = argparse.ArgumentParser(description='Batch merge GitLab merge requests from JSON lists.')
    parser.add_argument('--vendor_source_file', default='qssi_mr_list.json', help='source vendor mr list')
    parser.add_argument('--qssi_source_file', default='vendor_mr_list.json', help='source qssi mr list')
    parser.add_argument('--qnx_source_file', default='qnx_mr_list.json', help='source qnx mr list')
    parser.add_argument('--qfile_source_file', default='amss_mr_list.json', help='source qfile mr list')
    parser.add_argument('--vendor_target_file', default='vendor_mr_list.json', help='local vendor target file')
    parser.add_argument('--qssi_target_file', default='qssi_mr_list.json', help='local qssi target file')
    parser.add_argument('--qnx_target_file', default='qnx_mr_list.json', help='local qnx target file')
    parser.add_argument('--qfile_target_file', default='amss_mr_list.json', help='local qfile target file')
    args = parser.parse_args()

    vendor_source_file = args.vendor_source_file
    qssi_source_file = args.qssi_source_file
    qnx_source_file = args.qnx_source_file
    qfile_source_file = args.qfile_source_file

    vendor_target_file = args.vendor_target_file
    qssi_target_file = args.qssi_target_file
    qnx_target_file = args.qnx_target_file
    qfile_target_file = args.qfile_target_file

    # 删除之前的下载的json文件
    patterns = ["*.txt", "*.json", "*.xlsx"]
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            os.remove(file_path)

    # 如果 artifactory 配置存在，则尝试下载
    if artifactory_url and token:
        down_vendor = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(vendor_source_file, vendor_target_file, artifactory_url, token)
        down_qssi = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(qssi_source_file, qssi_target_file, artifactory_url, token)
        down_qnx = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(qnx_source_file, qnx_target_file, artifactory_url, token)
        down_qfile = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(qfile_source_file, qfile_target_file, artifactory_url, token)

        result1 = run_cmd(down_vendor)
        print(f"[download] vendor rc={result1.returncode} stdout={result1.stdout.strip()} stderr={result1.stderr.strip()}")
        result2 = run_cmd(down_qssi)
        print(f"[download] qssi rc={result2.returncode} stdout={result2.stdout.strip()} stderr={result2.stderr.strip()}")
        result3 = run_cmd(down_qnx)
        print(f"[download] qnx rc={result3.returncode} stdout={result3.stdout.strip()} stderr={result3.stderr.strip()}")
        result4 = run_cmd(down_qfile)
        print(f"[download] qnx rc={result4.returncode} stdout={result4.stdout.strip()} stderr={result4.stderr.strip()}")
    else:
        print("[main] 未提供 artifactory 配置，跳过下载步骤。")

    # 使用解析/传入的 target 文件名
    load_mr_list_from_file(vendor_target_file)
    load_mr_list_from_file(qssi_target_file)
    load_mr_list_from_file(qnx_target_file)
    load_mr_list_from_file(qfile_target_file)
    print("\033[1;32m 如果执行完发现有mr还没有merge,需要再跑一遍! \033[0m")
    print("\033[1;32m 如果执行完发现有mr还没有merge,需要再跑一遍! \033[0m")
