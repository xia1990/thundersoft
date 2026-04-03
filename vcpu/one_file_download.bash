#!/bin/bash
source ${HOME}/.env


source_file=$1
target_file=$2

if [ -z "$target_file" ] || [ -z "$source_file" ]; then
	echo -e " \e[31m 请输入2个参数：\e[0m "
	echo -e " \e[31m source_file="a/build/b/d/e/master/5774"  \e[0m"
	echo -e " \e[31m target_file="E227.0-5774" \e[0m "
	exit 0
else
	echo -e "开如下载-------------------------------------------------"
    rm -rf $target_file
    echo "jf rt dl "$source_file" "$target_file" --url="$artifactory_url" --user="$username" --password="$api_key" --flat=true"
	jf rt dl "$source_file" "$target_file" --url="$artifactory_url" --user="$username" --password="$api_key" --flat=true
	# jf rt dl "$source_file" "$target_file" --url=https://artifacts.sb.com/artifactory/ --user=GAYUXIA --password=pwd --flat=true
fi
