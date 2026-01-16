#!/usr/bin/env python3
"""
修复智能体LLM调用，使用get_agent_llm而不是get_default_model
"""
import re
from pathlib import Path

# 定义需要修改的智能体文件和对应的agent名称
AGENT_FILES = {
    "app/agents/agents/sql_generator_agent.py": "CORE_AGENT_SQL_GENERATOR",
    "app/agents/agents/schema_agent.py": "CORE_AGENT_SQL_GENERATOR",  # schema也用SQL生成器的配置
    "app/agents/agents/error_recovery_agent.py": "CORE_AGENT_SQL_GENERATOR",  # 错误恢复也用SQL生成器的配置
}

def fix_agent_file(file_path: str, agent_const: str):
    """修复单个智能体文件"""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    content = path.read_text(encoding='utf-8')
    original_content = content
    
    # 1. 添加导入语句（如果不存在）
    if "from app.core.agent_config import" not in content:
        # 找到 from app.core.llms import 这一行
        import_pattern = r'(from app\.core\.llms import [^\n]+)'
        replacement = r'\1\nfrom app.core.agent_config import get_agent_llm, ' + agent_const
        content = re.sub(import_pattern, replacement, content)
        print(f"  ✓ 添加导入语句")
    
    # 2. 替换所有 llm = get_default_model() 为 llm = get_agent_llm(AGENT_NAME)
    pattern = r'llm = get_default_model\(\)'
    replacement = f'llm = get_agent_llm({agent_const})'
    count = len(re.findall(pattern, content))
    if count > 0:
        content = re.sub(pattern, replacement, content)
        print(f"  ✓ 替换了 {count} 处 get_default_model() 调用")
    
    # 3. 替换 self.llm = get_default_model() 为 self.llm = get_agent_llm(AGENT_NAME)
    pattern2 = r'self\.llm = get_default_model\(\)'
    replacement2 = f'self.llm = get_agent_llm({agent_const})'
    count2 = len(re.findall(pattern2, content))
    if count2 > 0:
        content = re.sub(pattern2, replacement2, content)
        print(f"  ✓ 替换了 {count2} 处 self.llm = get_default_model() 调用")
    
    if content != original_content:
        path.write_text(content, encoding='utf-8')
        print(f"✅ 已修复: {file_path}")
        return True
    else:
        print(f"⚠️  无需修改: {file_path}")
        return False

def main():
    print("开始修复智能体LLM调用...")
    print("="*80)
    
    fixed_count = 0
    for file_path, agent_const in AGENT_FILES.items():
        print(f"\n处理: {file_path}")
        print(f"  使用配置: {agent_const}")
        if fix_agent_file(file_path, agent_const):
            fixed_count += 1
    
    print("\n" + "="*80)
    print(f"完成！共修复 {fixed_count} 个文件")
    print("\n注意：")
    print("1. chart_generator_agent 已经支持自定义LLM，无需修改")
    print("2. supervisor_agent 使用全局默认LLM，无需修改")
    print("3. sql_executor_agent 不需要LLM，无需修改")

if __name__ == "__main__":
    main()
