#!/bin/bash

source $HOME/.env

DELETE_FILE=$1
# PATTERN="*unencrypted*.tar"

if [ -z "$DELETE_FILE" ]; then
	echo -e " \e[31m 请输入你要删除的文件：\e[0m "
	echo -e " \e[31m DELETE_FILE="sb/sb/sn/20250522/E229.0/System_444712/deliverables/STAR3.0/swup/a.txt" \e[0m "
	exit 0
fi

# 第一步：列出将要删除的文件
echo "即将删除以下文件：" 
jf rt s "$DELETE_FILE" --url=$ARTIFACTORY_URL_SWF \
  --user=$ARTIFACTORY_USER \
  --password=$API_KEY_SWF \
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
jf rt del "$DELETE_FILE" \
  --url="$ARTIFACTORY_URL_SWF" \
  --user="$ARTIFACTORY_USER" \
  --password="$API_KEY_SWF" \
  --recursive \
  --quiet 

echo "删除完成。" 
