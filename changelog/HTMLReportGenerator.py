import pdfkit
import re

GITLAB_BASE_URL = "https://git.gitlab.com"
SWF_GITLAB_URL = "https://git.gitlab.com"

class HTMLReportGenerator:
    def __init__(self, output_html="commit_report.html", output_pdf="commit_report.pdf"):
        self.output_html = output_html
        self.output_pdf = output_pdf

    def generate(self, diff_data):
        html_content = self._generate_html_content(diff_data)
        
        self._write_to_file(html_content)
        self._convert_to_pdf()

    def _generate_html_content(self, diff_data):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>General Changes</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }
                .timestamp { color: #666; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { padding: 12px 15px; border: 1px solid #ddd; text-align: left; }
                th { background-color: #f8f9fa; position: sticky; top: 0; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .repo-header { background-color: #e7f5ff !important; font-weight: bold; }
                .commit-id { font-family: monospace; }
                .error { color: #dc3545; }
            </style>
        </head>
        <body>
            <h1>General Changes</h1>
            <div class="timestamp">Changes of subsystem in GitLab: android, qnx, VCPU</div>
            <table>
                <thead>
                    <tr>
                        <th width="15%">Commit</th>
                        <th width="15%">Author</th>
                        <th width="55%">Message</th>
                        <th width="15%">Jira-ID</th>
                    </tr>
                </thead>
                <tbody>
        """
        # 如果两个版本之间没有修改记录
        if not diff_data:
            html += """
            <tr>
                <td colspan="4" class="no-data">📭 No repository differences found</td>
            </tr>
            """
        else:
            for repo_data in diff_data:
                html += f"""
                    <tr class="repo-header">
                        <td colspan="4">
                            {repo_data.get("repo_name")} | 
                            version: {repo_data['old_rev'][:8]}..{repo_data['new_rev'][:8]}
                        </td>
                    </tr>
                """

                if 'error' in repo_data:
                    html += f"""
                    <tr>
                        <td colspan="4" class="error">⚠️ {repo_data['error']}</td>
                    </tr>
                    """
                else:
                    # 检查 commits 是否为空
                    commits = repo_data.get('commits', [])
                    if not commits:
                        html += f"""
                        <tr>
                            <td colspan="4" class="no-changes">No changes in {repo_data['repo_name']}</td>
                        </tr>
                        """
                    else:
                        for commit in commits:
                            base_url = SWF_GITLAB_URL if "vcpu" in repo_data['repo_name'].lower() else GITLAB_BASE_URL
                            commit_link = f"""
                            <a href="{base_url}/{repo_data['repo_name']}/-/commit/{commit['id']}" 
                                target="_blank" title="View commit">
                                {commit['short_id']}
                            </a>
                            """

                            message = commit.get("message", "")
                            jira_id = 'N/A'
                            if 'APRICOT' in message:
                                matches = re.findall(r'(APRICOT.*?\d+)', message)
                                jira_id = matches[0] if matches else 'No Jira-ID Found'

                            html += f"""
                            <tr>
                                <td class="commit-id">{commit_link}</td>
                                <td>{commit['author_name']}</td>
                                <td>{commit['title']}</td>
                                <td>{jira_id}</td>
                            </tr>
                            """

        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return html

    def _write_to_file(self, content):
        with open(self.output_html, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 报告已生成：{self.output_html}")

    def _convert_to_pdf(self):
        try:
            pdfkit.from_file(self.output_html, self.output_pdf)
            print(f"✅ PDF 已生成：{self.output_pdf}")
        except Exception as e:
            print(f"❌ PDF 转换失败: {e}")