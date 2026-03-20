#!/bin/bash
#_*_ coding:utf-8_*_

python3 merge_mr.py \
--vendor_source_file sb/sb/sb/20260108/E245.0/System_823054/deliverables/android/dev/STAR3.0/vendor_mr_list.json \
--qssi_source_file sb/sb/sb/20260108/E245.0/System_823054/deliverables/android/dev/STAR3.0/qssi_mr_list.json \
--qnx_source_file sb/sb/sb/20260108/E245.0/System_823054/deliverables/qnx/dev/STAR3.0/SA8295/qnx_mr_list.json 
#--amss_source_file sb/sb/sb/20250719/E233.0/System_511853/deliverables/STAR3.0/android/prod-rl/amss_mr_list.json 
