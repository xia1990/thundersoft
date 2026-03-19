#_*_ coding:utf-8_*_

import json
import pandas as pd
import argparse
import re

def process_mr_data(input_json, output_excel):
    """处理MR数据并生成Excel文件"""
    try:
        # 读取 JSON 文件
        with open(input_json, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # 提取字段并处理 TMXS 链接
        extracted_data = []
        for index, item in enumerate(data, start=1):
            tmx_id = item['tmxs']
            #tmx_id = item['Regression']
            ticket_id = item['tickets']
            # 处理 Test Info 链接
            if tmx_id:
                test_info = f'=HYPERLINK("https://issue.sb.com/browse/{tmx_id}", "{tmx_id}")'
            else:
                test_info = ""
            
            # 处理 Apricot Ticket 链接
            if ticket_id:
                apricot_ticket = f'=HYPERLINK("https://issue.sb.com/browse/{ticket_id}", "{ticket_id}")'
            else:
                apricot_ticket = ""

            # 处理 MR 链接
            mr_url = item['path_with_namespace']
            mr_iid = item['mr_iid']
            if mr_url:
                MR = f'=HYPERLINK("https://git.sb.com/{mr_url}/merge_requests/{mr_iid}", "{mr_url}")'
            else:
                MR = ""


            # 处理 REQ 字段（如果不是以REQ-开头则设为空）
            req_value = item['reqs']
            if req_value and not re.fullmatch(r'REQ-', req_value.strip()):
                req_value = ""
            
            extracted_data.append({
                'Index': index,
                'Merge Request URL': MR,
                'Merge Message': item['title'],
                'REQ': item['reqs'],  # 使用处理后的值
                'Apricot Ticket': apricot_ticket,
                'Domain': item['domain'],
                'Test Info': test_info
            })

        # 创建 DataFrame 并写入 Excel
        df = pd.DataFrame(extracted_data)
        
        # 设置列顺序
        columns = ['Index'] + [col for col in df.columns if col != 'Index']
        df = df[columns]
        
        df.to_excel(output_excel, index=False, engine='openpyxl')
        print(f"数据已成功写入 {output_excel}")

    except FileNotFoundError:
        print(f"错误：输入文件 {input_json} 不存在")
    except json.JSONDecodeError:
        print(f"错误：{input_json} 不是有效的JSON文件")
    except Exception as e:
        print(f"发生未知错误：{str(e)}")

if __name__ == "__main__":
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='处理MR数据并生成Excel文件')
    parser.add_argument('-i', '--input', required=True, help='输入的JSON文件路径')
    parser.add_argument('-o', '--output', default='merge_requests.xlsx', 
                       help='输出的Excel文件路径（默认：merge_requests.xlsx）')
    
    args = parser.parse_args()
    process_mr_data(args.input, args.output)
