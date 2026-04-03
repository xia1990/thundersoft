source $HOME/.env



source_file=$1
target_file=$2

if [ "$#" -ne 2 ];then
    echo 'source_file="a/b//logical-blocks-i3-AC-STAR30_unencrypted.tar"'
    echo 'target_file="b/d/E228.0/deliverables/swup/dev/STAR3.0/AC/WLD/"'
    exit 1
else
    # jf rt copy "$1" "$2"
    jf rt copy "$1" "$2"  --url=$artifactory_url \
    --user=$username \
    --password=$api_key \
    --insecure-tls=false \
    --flat=true
fi
