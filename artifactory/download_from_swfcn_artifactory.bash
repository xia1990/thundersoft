#!/bin/bash
# 从SWFCN批量下载指定目录下的所有内容，包括子目录下的所有内容，到本地指定目录
source $HOME/.env
IFS="
"

LOCAL_DIR="./System_508582/"


echo "Source Path: '$REPO_PATH'"
echo "Local Dir:   '$LOCAL_DIR'"
mkdir -p "$LOCAL_DIR"

for REPO_PATH in `cat json_path.txt`
do
    # 执行下载
    echo ">>> jf rt dl "$REPO_PATH" "$LOCAL_DIR" --url="$artifactory_url" --user="GAYUXIA" --password="$api_key" --recursive --threads=8 --verbose"
    # 保持目录结构下载
    jf rt dl "$REPO_PATH" "$LOCAL_DIR" --url="$artifactory_url" --user="GAYUXIA" --password="$api_key" --recursive 
    # break
done
