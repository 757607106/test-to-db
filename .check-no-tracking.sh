#!/bin/bash

# 检查项目中是否存在版权追踪标记
# 用法: ./.check-no-tracking.sh

echo "🔍 检查项目中的版权追踪标记..."

# 搜索所有源代码文件中的追踪标记
TRACKING_FILES=$(find . -type f \
  \( -name "*.js" -o -name "*.mjs" -o -name "*.ts" -o -name "*.tsx" -o -name "*.json" -o -name "*.py" \) \
  ! -path "*/node_modules/*" \
  ! -path "*/.next/*" \
  ! -path "*/dist/*" \
  ! -path "*/__pycache__/*" \
  -exec grep -l "MS8[0-9yOm]" {} \; 2>/dev/null)

if [ -z "$TRACKING_FILES" ]; then
  echo "✅ 未发现版权追踪标记！"
  exit 0
else
  echo "❌ 发现以下文件包含版权追踪标记："
  echo "$TRACKING_FILES"
  echo ""
  echo "请运行清理脚本: ./.remove-tracking.sh"
  exit 1
fi
