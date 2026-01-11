#!/bin/bash

# 自动清除项目中的版权追踪标记
# 用法: ./.remove-tracking.sh

echo "🧹 开始清除版权追踪标记..."

python3 <<'EOF'
import os
import re
import subprocess

# 查找所有包含追踪标记的文件
result = subprocess.run(
    ['find', '.', '-type', 'f',
     '(', '-name', '*.js', '-o', '-name', '*.mjs', '-o', '-name', '*.ts', 
     '-o', '-name', '*.tsx', '-o', '-name', '*.json', '-o', '-name', '*.py', ')',
     '!', '-path', '*/node_modules/*',
     '!', '-path', '*/.next/*',
     '!', '-path', '*/dist/*',
     '!', '-path', '*/__pycache__/*'],
    capture_output=True,
    text=True
)

all_files = result.stdout.strip().split('\n') if result.stdout.strip() else []

# 通用的追踪标记清理正则
pattern = re.compile(r'^[#/]+\s*[^MS]*\s*MS8[0-9A-Za-z+/=]+\s*$', re.MULTILINE)

cleaned_count = 0
error_count = 0

for file_path in all_files:
    if not file_path or not os.path.exists(file_path):
        continue
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否包含追踪标记
        if not re.search(r'MS8[0-9A-Za-z+/=]+', content):
            continue
        
        original_content = content
        
        # 清理追踪标记
        content = pattern.sub('', content)
        
        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            cleaned_count += 1
            print(f"✓ 已清理: {file_path}")
    except Exception as e:
        error_count += 1
        print(f"✗ 错误: {file_path}: {e}")

print(f"\n总计清理文件: {cleaned_count}")
print(f"错误数量: {error_count}")

if cleaned_count > 0:
    print("\n✅ 版权追踪标记已清除完毕！")
else:
    print("\n✅ 未发现需要清理的追踪标记！")
EOF
