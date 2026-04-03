#!/bin/bash
source ${HOME}/.env
file=$1
upload_dir=$2

if [ $# -ne 2 ];then
    echo "请输入2个参数：要上传的文件，上传到的目录"
    exit 0
else
    jf rt u --fail-no-op --recursive=true --flat=true --url $artifactory_url $file $upload_dir --user=$username --password=$api_key
fi
