#!/bin/bash


root_path=`pwd`

rm -rf gitlog
mkdir -p gitlog
IFS="
"
for path in `repo list -p`
do
    pushd $path
        mkdir -p $root_path/gitlog/$path
        git log --pretty=oneline  --no-decorate -n 100 | tee $root_path/gitlog/$path/git.log
    popd
done

