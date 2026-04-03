source ${HOME}/.env

upload_dir=$1
local_dir=$2

if [ $# -ne 2 ];then
    echo "请输入如下2个参数："
    echo 'upload_dir="apricot_rse/i3_RSU/VCPU/8295_master/STAR3.0"'
    echo 'local_dir="E228.0-1372"'
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
