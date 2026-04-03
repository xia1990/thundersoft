#_*_ coding:utf-8_*_

import json
import pandas as pd
import argparse
import re
from configparser import ConfigParser
import subprocess
import os
import glob

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


def process_mr_data(input_json, sheet_name):
    """处理MR数据并返回DataFrame"""
    try:
        # 读取 JSON 文件
        with open(input_json, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # 提取字段并处理
        extracted_data = []
        for index, item in enumerate(data, start=1):
            tmx_id = item.get('tmxs')
            ticket_id = item.get('tickets')

            # Test Info 链接
            test_info = f'=HYPERLINK("https://issue.sb.com/browse/{tmx_id}", "{tmx_id}")' if tmx_id else ""

            # Apricot Ticket 链接
            apricot_ticket = f'=HYPERLINK("https://issue.sb.com/browse/{ticket_id}", "{ticket_id}")' if ticket_id else ""

            # MR 链接
            mr_url = item.get('path_with_namespace')
            mr_iid = item.get('mr_iid')
            MR = f'=HYPERLINK("https://git.sb.com/{mr_url}/merge_requests/{mr_iid}", "{mr_url}")' if mr_url else ""

            # 处理 REQ 字段
            req_value = item.get('reqs')
            if req_value and not re.fullmatch(r'REQ-', req_value.strip()):
                req_value = ""

            extracted_data.append({
                'Index': index,
                'Merge Request URL': MR,
                'Merge Message': item.get('title', ''),
                'REQ': req_value,
                'Apricot Ticket': apricot_ticket,
                'Domain': item.get('domain', ''),
                'Test Info': test_info
            })

        df = pd.DataFrame(extracted_data)

        # 保证 Index 在第一列
        columns = ['Index'] + [col for col in df.columns if col != 'Index']
        df = df[columns]
        return sheet_name, df
    except Exception as e:
        print(f"处理 {input_json} 时出错: {e}")
        return sheet_name, pd.DataFrame()  # 返回空表


if __name__ == "__main__":
    # 加载环境变量
    config = ConfigParser()
    config.read("/home/GAYUXIA/config.ini")
    
    # 获取配置参数
    PRIVATE_TOKEN = config.get("gitlab", "token")
    GITLAB_URL = config.get("gitlab", "url")
    GROUP_PATH = "RSE"
    artifactory_url = config.get("artifact", "url")
    artifactory_token = config.get("artifact", "token")
    user = config.get("artifact", "username")
    
    # 设置命令行参数
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
    
    # 定义文件配置和处理
    file_configs = [
        (args.source_vendor_file, "vendor_mr_list.json", "Vendor_Data"),
        (args.source_qssi_file, "qssi_mr_list.json", "QSSI_Data"),
        (args.source_qnx_file, "qnx_mr_list.json", "QNX_Data"),
        (args.source_amss_file, "amss_mr_list.json", "AMSS_Data"),
    ]
    
    dfs = []
    # 下载并处理数据
    for source_file, json_name, sheet_name in file_configs:
        if not source_file:
            print(f"警告: 缺少源文件参数，跳过 {sheet_name}")
            continue

        print(f"处理: {source_file} -> {json_name} -> {sheet_name}")
        try:
            # 下载 JSON 文件 (需自带 get_mr_json_file 函数)
            get_mr_json_file(artifactory_url, artifactory_token, source_file, json_name)

            if os.path.exists(json_name):
                sheet, df = process_mr_data(json_name, sheet_name)
                if not df.empty:
                    dfs.append((sheet, df))
                    print(f"成功获取: {sheet_name}")
                else:
                    print(f"{sheet_name} 无有效数据")
            else:
                print(f"错误: JSON文件 {json_name} 不存在，跳过")
        except Exception as e:
            print(f"处理 {source_file} 时发生错误: {e}")

    # 统一写入一个Excel
    if dfs:
        with pd.ExcelWriter(args.output_excel, engine="openpyxl") as writer:
            for sheet, df in dfs:
                df.to_excel(writer, sheet_name=sheet, index=False)
        print(f"✅ 所有数据已合并写入 {args.output_excel}")
    else:
        print("❌ 没有可写入的数据")
    

