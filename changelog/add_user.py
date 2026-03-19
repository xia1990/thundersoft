import os
from pathlib import Path
import sys

def find_all_codeowners_files(root_dir='.'):
    """查找所有 CODEOWNERS 文件并返回路径列表"""
    root_path = Path(root_dir).resolve()
    return [str(p) for p in root_path.rglob('CODEOWNERS') if p.is_file()]

def add_codeowner_to_files(file_paths, new_owner="@GAYUXIA"):
    """向 CODEOWNERS 文件添加新所有者"""
    for file_path in file_paths:
        try:
            with open(file_path, 'r+', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 处理每一行
                new_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        new_lines.append(line + '\n')
                        continue
                    
                    # 检查是否已包含该所有者
                    if new_owner in line.split():
                        new_lines.append(line + '\n')
                        continue
                    
                    # 添加新所有者
                    new_lines.append(line + ' ' + new_owner + '\n')
                
                # 写回文件
                f.seek(0)
                f.writelines(new_lines)
                f.truncate()
                
            print(f"成功更新: {file_path}")
        except Exception as e:
            print(f"处理 {file_path} 时出错: {str(e)}")

if __name__ == '__main__':
    # 1. 查找所有 CODEOWNERS 文件
    codeowners_files = find_all_codeowners_files()
    
    if not codeowners_files:
        print("未找到任何 CODEOWNERS 文件")
        exit()
    
    print(f"找到 {len(codeowners_files)} 个 CODEOWNERS 文件:")
    for i, file_path in enumerate(codeowners_files, 1):
        print(f"{i}. {file_path}")
    
    # 2. 添加所有者
    print("\n正在添加 @GAYUXIA 到这些文件中...")
    add_codeowner_to_files(codeowners_files)
    
    print("\n操作完成!")
