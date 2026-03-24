# 检查confluence page页面上面删除的MR，并把它加入到黑名单中
# https://wiki.sb.com/display/APRICOT/RSU+MR+Review+Meeting
import requests
from requests.auth import HTTPBasicAuth
import json
from bs4 import BeautifulSoup
import sys

CONFLUENCE_BASE_URL = "https://wiki.sb.com"
API_TOKEN = ""  
EMAIL = "thundersoft.yuxia@mercedes-benz.com"  

def get_black_list_mr():
    api_url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{PAGE_ID}?expand=body.storage,version"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}"
    }

    response = requests.get(
        api_url,
        headers=headers
    )

    if response.status_code == 200:
        print("请求成功！")   
        data = response.json()   
        print(f"页面标题: {data['title']}")
        print(f"版本号: {data['version']['number']}")
        
        # 打印页面内容 (HTML 格式)
        # 内容存储在 data['body']['storage']['value']
        page_content_html = data['body']['storage']['value']
        soup = BeautifulSoup(page_content_html, 'html.parser')
        
        # 查找所有的 <s> 标签
        s_tags = soup.find_all('s')
        
        # print(f"\033[1;31m 找到 {len(s_tags)} 个 <s> 标签 \033[0m")
        print("-" * 50)
        # 提取并打印每个 <s> 标签中的内容
        for i, s_tag in enumerate(s_tags, 1):
            # 获取标签内的文本内容，去除首尾空白
            content = s_tag.get_text(strip=True)  
            print(f"\033[1;31m 删除MR列表: \033[0m")
            print(f"{i}. {content}")
        
        # 将所有带有s标签的内容存入黑名单列表
        black_list = [tag.get_text(strip=True) for tag in s_tags]
        # print(black_list)
        print("-" * 50)
        # （可选）将提取的内容保存到文件
        with open('s_tag_contents.txt', 'w', encoding='utf-8') as f:
            for content in black_list:
                f.write(content + '\n')
        print("\n<s> 标签内容已保存到 'black_list.txt'")
    
        # （可选）将完整响应保存到 JSON 文件以便查看
        with open('confluence_page_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print("\n完整响应已保存到 'confluence_page_data.json'")
        
    else:
        print(f"请求失败，状态码: {response.status_code}")
        print(response.text)

if __name__ == '__main__':
    if len(sys.argv) < 2: 
        print("\033[31m 请传入一个pageID \033[0m")
        sys.exit(1)
    else:
        PAGE_ID = sys.argv[1]
        get_black_list_mr()
