import requests
from requests.auth import HTTPBasicAuth

def delete_confluence_page(page_id, username, api_token):
    """
    删除 Confluence Data Center/Server 页面
    :param page_id: 页面 ID
    :param username: 用户名（必须有删除权限）
    :param password: 用户密码
    """
    base_url = "https://wiki.sb.com/"
    api_url = f"{base_url}/rest/api/content/{page_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token}"
    }

    try:
        response = requests.delete(api_url, headers=headers, timeout=30)
        if response.status_code == 204:
            print(f"✅ 页面 {page_id} 删除成功")
            return True
        else:
            print(f"❌ 删除失败 (HTTP {response.status_code}): {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"🔴 请求出错: {str(e)}")
        return False

# 使用示例
delete_confluence_page(
    page_id="1234567890",
    username="GAYUXIA",
    api_token="token"
)
