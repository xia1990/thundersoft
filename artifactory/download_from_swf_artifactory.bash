#!/bin/bash
# 从SWF批量下载指定目录下的所有内容，包括子目录下的所有内容，到本地指定目录
source $HOME/.env


REPO_PATH="a/b/c/20250816/E234.1/System_548583/deliverables/STAR3.0/swup/prod-rl/STAR3.0/20250816_548583_user_7984/"
LOCAL_DIR="."

echo "Source Path: '$REPO_PATH'"
echo "Local Dir:   '$LOCAL_DIR'"
mkdir -p "$LOCAL_DIR"

# 执行下载
echo ">>> jf rt dl "$REPO_PATH" "$LOCAL_DIR" --url="$ARTIFACTORY_URL" --user="GAYUXIA" --password="$API_KEY_SWF" --recursive --threads=8 --verbose"
# 保持目录结构下载
jf rt dl "$REPO_PATH" "$LOCAL_DIR" --url="$ARTIFACTORY_URL" --user="GAYUXIA" --password="$API_KEY_SWF" --recursive 
