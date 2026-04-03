#!/bin/bash

source ${HOME}/.env
target_dir=$1

#要下载的repo path
source_url=$2

if [ -z "$target_dir" ] || [ -z "$source_url" ]; then
	echo -e " \e[31m 请输入2个参数：\e[0m "
	echo -e " \e[31m target_dir="E227.0-5774" \e[0m "
	echo -e " \e[31m source_url="a/build/c/d/e/master/5774"  \e[0m"
	exit 0
else
	echo "target_dir:$target_dir"
	echo "source_url:$source_url"

	rm -rf $target_dir
	# 下载
	echo -e "开如下载--------------------------------------------------------"
	#--flat=false: 表示保留原始目录结构（如果是 true，则所有文件会扁平化下载到同一个目录中）
    echo "jf rt dl "$source_url/dev/" "$target_dir/dev/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true"
	jf rt dl "$source_url/dev/" "$target_dir/dev/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true --retries=5 --threads=6 --retry-wait-time=10s --split-count=15
    echo "jf rt dl "$source_url/prod/" "$target_dir/prod/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true"
	jf rt dl "$source_url/prod/" "$target_dir/prod/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true --retries=5 --threads=6 --retry-wait-time=10s --split-count=15
    echo "jf rt dl "$source_url/prod-pl/" "$target_dir/prod-pl/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=tru"
	jf rt dl "$source_url/prod-pl/" "$target_dir/prod-pl/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true --retries=5 --threads=6 --retry-wait-time=10s --split-count=15
    echo "jf rt dl "$source_url/prod-rl/" "$target_dir/prod-rl/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true"
	jf rt dl "$source_url/prod-rl/" "$target_dir/prod-rl/" --url="$ARTIFACTORY_URL_SWF" --user="GAYUXIA" --password="$API_KEY_SWF" --flat=true --retries=5 --threads=6 --retry-wait-time=10s --split-count=15
	echo -e "\e[32m 下载结束------------------------------------------------- \e[0m"
fi
 

