#_*_ coding:utf-8_*_

import json
import pandas as pd
import argparse
import re
from configparser import ConfigParser
import subprocess
import os
import glob
import sys

def shell(command, result=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
    # 获取命令的输出结果
    stdout, stderr = process.communicate()
    # 等待命令执行完成，wait() 返回进程的返回码
    return_code = process.wait()
    # if 1:
    if result:
        # 根据返回码判断命令是否成功执行
        if return_code == 0:
            pass
        else:
            print(command,': 命令执行失败', return_code)
    return return_code, stdout.decode()

    
def get_mr_json_file(artifactory_url, token, source_file,target_file):
    down_command = "jf rt dl \"{}\" \"{}\" --url={} --user=GAYUXIA --password={} --flat=true".format(source_file,target_file,artifactory_url,token)
    status,result = shell(down_command,result=True)  


def process_mr_data(input_json):
    """处理MR数据并返回DataFrame（不含Index）"""
    try:
        # 读取 JSON 文件
        with open(input_json, 'r', encoding='utf-8') as file:
            data = json.load(file)
        extracted_data = []
        for item in data:
            # tmx_id = item.get('tmxs')
            # ticket_id = item.get('tickets')

            # Test Info 链接
            # test_info = f'=HYPERLINK("https://issue.sb.com/browse/{tmx_id}", "{tmx_id}")' if tmx_id else ""

            # Apricot Ticket 链接
            # apricot_ticket = f'=HYPERLINK("https://issue.sb.com/browse/{ticket_id}", "{ticket_id}")' if ticket_id else ""

            # MR 链接
            # mr_url = item.get('path_with_namespace')
            # mr_iid = item.get('mr_iid')
            # MR = f'=HYPERLINK("https://git.sb.com/{mr_url}/merge_requests/{mr_iid}", "{mr_url}")' if mr_url else ""

            # 处理 REQ 字段
            req_value = item.get('reqs')
            
            if req_value and not re.fullmatch(r'REQ-', req_value.strip()):
                req_value = ""
            else:
                if "bug" in req_value.lower():
                    mr_iid = item.get('mr_iid')
                    print(mr_iid)
                    
            extracted_data.append({
                # 'Merge Request URL': mr_iid,
                # 'Merge Message': item.get('title', ''),
                'REQ': req_value
                # 'Apricot Ticket': apricot_ticket,
                # 'Domain': item.get('domain', ''),
                # 'Test Info': test_info
            })

        return pd.DataFrame(extracted_data)

    except Exception as e:
        print(f"处理 {input_json} 时出错: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    # 加载配置
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")

    PRIVATE_TOKEN = config.get("gitlab", "token")
    GITLAB_URL = config.get("gitlab", "url")
    GROUP_PATH = "RSE"
    artifactory_url = config.get("artifact", "url")
    artifactory_token = config.get("artifact", "token")
    user = config.get("artifact", "username")

    # 参数
    parser = argparse.ArgumentParser(description='处理MR数据并生成Excel文件')
    parser.add_argument("-v", '--source_vendor_file', required=True, help="vendor mr list file")
    parser.add_argument("-q", '--source_qssi_file', required=True, help="qssi mr list file")
    parser.add_argument("-n", '--source_qnx_file', required=True, help="qnx mr list file")
    parser.add_argument("-a", '--source_amss_file', required=True, help="amss mr list file")
    parser.add_argument("-o", '--output_excel', default="all_mr_data.xlsx", help="最终合并的Excel文件")

    args = parser.parse_args()

    # 清理旧文件
    for pattern in ["*.json", "*.xlsx"]:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
                print(f"已删除: {file}")
            except OSError as e:
                print(f"删除文件 {file} 时出错: {e}")

    # 配置文件
    file_configs = [
        (args.source_vendor_file, "vendor_mr_list.json"),
        (args.source_qssi_file, "qssi_mr_list.json"),
        (args.source_qnx_file, "qnx_mr_list.json"),
        (args.source_amss_file, "amss_mr_list.json"),
    ]

    all_dfs = []

    # 下载并处理数据
    for source_file, json_name in file_configs:
        if not source_file:
            print(f"警告: 缺少源文件参数，跳过 {json_name}")
            continue

        print(f"处理: {source_file} -> {json_name}")
        try:
            # 下载 JSON 文件 (需自带 get_mr_json_file 函数)
            get_mr_json_file(artifactory_url, artifactory_token, source_file, json_name)

            if os.path.exists(json_name):
                df = process_mr_data(json_name)
                if not df.empty:
                    if all_dfs:
                        # 合并去重，避免重复数据
                        combined = pd.concat([pd.concat(all_dfs, ignore_index=True), df], ignore_index=True)
                        # 默认的 drop_duplicates() 比较的是 整行的所有列的值
                        # 只有当一行里 所有列的值完全相同 时，才会被认为是重复并删除
                        combined = combined.drop_duplicates(ignore_index=True)
                        all_dfs = [combined]   # 只保留去重后的DataFrame
                    else:
                        all_dfs.append(df)
                    print(f"成功获取: {json_name}，已去重追加")
                else:
                    print(f"{json_name} 无有效数据")
            else:
                print(f"错误: JSON文件 {json_name} 不存在，跳过")
        except Exception as e:
            print(f"处理 {source_file} 时发生错误: {e}")

    # 合并所有DataFrame，写入一个工作表
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)

        # 添加全局递增 Index
        final_df.insert(0, "Index", range(1, len(final_df) + 1))

        final_df.to_excel(args.output_excel, sheet_name="All_Data", index=False, engine="openpyxl")
        print(f"✅ 所有数据已合并写入 {args.output_excel} 的 [All_Data] 工作表，Index 为全局递增编号")
    else:
        print("❌ 没有可写入的数据")


    

