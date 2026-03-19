#!/bin/bash

# changelog_generator.sh

set -e  # 遇到错误立即退出

# 配置变量
PYTHON_SCRIPT="make_changelog.py"
CONFIG_FILE="/home/gaoyuxia/config.ini"

# 基础参数
BUILD_RELEASE="E242.0"
GITLAB_BUILD_URL="https://git.sb.com/mercedes-ci/trigger/rsu-system-staging/-/pipelines/735463"
SOURCE_TAG="E241.0-47.1"
TARGET_TAG="E242.0-48.5"
VCPU_TAG="sb..sb"
CHANGELOG_TYPE="STAR3.5"

# Manifest文件参数
SOURCE_VENDOR_XML="sb/sb/sb/E241.0/deliverables/android/dev/STAR3.5/vendor_manifest.xml"
SOURCE_QSSI_XML="sb/sb/sb/E241.0/deliverables/android/dev/STAR3.5/qssi_manifest.xml" 
SOURCE_QNX_XML="sb/sb/sb/E241.0/deliverables/qnx/dev/STAR3.5/qnx_manifest.xml"

TARGET_QSSI_XML="Release_Integration/sb/E242.0/deliverables/android/dev/STAR3.0/qssi_manifest.xml"
TARGET_VENDOR_XML="Release_Integration/sb/E242.0/deliverables/android/dev/STAR3.0/vendor_manifest.xml"
TARGET_QNX_XML="Release_Integration/sb/E242.0/deliverables/qnx/dev/STAR3.0/qnx_manifest.xml"

VCPU_PATH="https://git.sb.com/apricotqal/civic-vcpu-rsu3.5.git"
# Word模板
WORD_URL="https://artifact.sb.com/artifactory/sb/sb/RSE_Temporary/GAYUXIA/changelog/E241.0_STAR3.5_changelog.docx"

echo "开始生成变更日志..."

python3 $PYTHON_SCRIPT \
    --build_release $BUILD_RELEASE \
    --gitlab_build_url $GITLAB_BUILD_URL \
    --source_tag $SOURCE_TAG \
    --target_tag $TARGET_TAG \
    --vcpu_tag $VCPU_TAG \
    --changelog_type $CHANGELOG_TYPE \
    --source_vendor_xml $SOURCE_VENDOR_XML \
    --target_vendor_xml $TARGET_VENDOR_XML \
    --source_qssi_xml $SOURCE_QSSI_XML \
    --target_qssi_xml $TARGET_QSSI_XML \
    --source_qnx_xml $SOURCE_QNX_XML \
    --target_qnx_xml $TARGET_QNX_XML \
    --vcpu_url $VCPU_PATH \
    --word_url $WORD_URL

echo "变更日志生成完成!"