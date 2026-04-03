source ${HOME}/.env


#!/bin/bash

echo -e "\e[31m 此脚本需要到你要上传的目录下执行，不然会有目录结构问题\e[0m"
echo -e "\e[31m 此脚本需要到你要上传的目录下执行，不然会有目录结构问题\e[0m"


local_dir=$1
upload_dir=$2
if [ $# -ne 2 ];then
    echo "请输入如下2个参数："
    echo -e '\e[34m local_dir="20250816_548583_user" \e[m'
    echo -e '\e[34m upload_dir="a/b/RSE_System_Staging_Build/20250816/E234.1/System_548583/deliverables/STAR3.0/swup/prod-rl/STAR3.0/20250816_548583_user2"\e[m'
    exit 0
fi

find "$local_dir" -type f | while read -r FILE;do
    cd $local_dir
    FILE="${FILE#$local_dir/}"
    TARGET_PATH=$upload_dir/$local_dir/
    echo "$FILE to $TARGET_PATH"
    jf rt u --fail-no-op --recursive=true --flat=false --url $artifactory_url $FILE $TARGET_PATH --user=$username --password=$api_key
    cd -
done