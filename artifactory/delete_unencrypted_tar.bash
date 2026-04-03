#!/bin/bash

source $HOME/.env

REPO_PATH=$1
PATTERN="*unencrypted*.tar"

if [ -z "$REPO_PATH" ]; then
	echo -e " \e[31m 请输入你要删除的目录：\e[0m "
	echo -e " \e[31m REPO_PATH="a/b/RSE_System_Staging_Build/20250522/E229.0/System_444712/deliverables/STAR3.0/swup/" \e[0m "
	exit 0
fi

# 接下来你可以继续执行搜索或删除操作

echo "搜索路径：$REPO_PATH"
echo "匹配模式：$PATTERN"
echo "日志文件：$LOG_FILE"
echo

# 第一步：列出将要删除的文件
echo "即将删除以下文件：" 
jf rt s "$REPO_PATH/$PATTERN" --url=$artifactory_url \
  --user=$username \
  --password=$api_key \
  --insecure-tls=false \
 > "find.txt"



# 第二步：确认是否删除
echo
read -p "是否确认删除这些文件？(yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  echo "操作取消。" 
  exit 0
fi


# 第三步：执行删除操作
echo "开始删除..." 
jf rt del "$REPO_PATH/$PATTERN" \
  --url=$artifactory_url \
  --user=$username \
  --password=$api_key \
  --quiet > "delete.txt"

echo "删除完成。" 
