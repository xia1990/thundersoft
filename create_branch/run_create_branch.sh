#!/bin/bash
set -e  # 遇到错误立即退出
PYTHON_SCRIPT="create_branch.py"
CONFIG_FILE="/home/gayuxia/config.ini"

new_branch="E246.1"
vendor_source_file="sb/sb/sb/E246.0/deliverables/android/dev/STAR3.0/vendor_manifest.xml"
qssi_source_file="sb/sb/sb/E246.0/deliverables/android/dev/STAR3.0/qssi_manifest.xml"
qnx_source_file="sb/sb/sb/E246.0/deliverables/qnx/dev/STAR3.0/qnx_manifest.xml"


python $PYTHON_SCRIPT \
    --new_branch $new_branch \
    --vendor_source_file $vendor_source_file \
    --qssi_source_file $qssi_source_file \
    --qnx_source_file $qnx_source_file