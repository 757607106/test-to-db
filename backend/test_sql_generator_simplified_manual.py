"""
SQLGeneratorAgent手动测试 - 简化流程验证
验证SQL生成后直接进入执行阶段
"""
import asyncio
from langchain_core.messages import HumanMessage
from app.agents.agents.sql_generator_agent import SQLGeneratorAgent
from app.core.state import SQLMessageState


async def test_next_stage_is_execution():
    """
    属性 1: 流程跳过验证阶段
    验证: 需求 1.2, 2.3
    
    测试SQL生成后下一阶段是执行
    """
    print("\n测试1: SQL生成后进入执行阶段")
    
    agent = SQLGeneratorAgent()
    
    # 创建测试状态
    state = SQLMessageState(
        messages=[HumanMessage(content="查询所有用户")],
        connection_id=15,
        current_stage="sql_generation",
        retry_count=0,
        max_retries=3,
        error_history=[],
        schema_info={"users": {"columns": ["id", "name", "email"]}},
        agent_messages={}
    )
    
    try:
        result = await agent.process(state)
        
        # 验证current_stage
        if result["current_stage"] == "sql_execution":
            print(f"  ✅ 通过: 下一阶段是sql_execution")
            return True
        else:
            print(f"  ❌ 失败: 下一阶段是{result['current_stage']}，期望sql_execution")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False


async def test_no_validation_stage():
    """
    属性 1: 流程跳过验证阶段
    验证: 需求 1.2, 2.3
    
    测试不经过验证阶段
    """
    print("\n测试2: 不经过验证阶段")
    
    agent = SQLGeneratorAgent()
    
    state = SQLMessageState(
        messages=[HumanMessage(content="查询用户数量")],
        connection_id=15,
        current_stage="sql_generation",
        retry_count=0,
        max_retries=3,
        error_history=[],
        schema_info={"users": {"columns": ["id", "name"]}},
        agent_messages={}
    )
    
    try:
        result = await agent.process(state)
        
        # 验证结果中不包含validation
        result_str = str(result)
        
        if "sql_validation" not in result_str:
            print(f"  ✅ 通过: 结果中不包含sql_validation")
            return True
        else:
            print(f"  ❌ 失败: 结果中包含sql_validation")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False


def test_system_prompt_emphasizes_quality():
    """
    测试系统提示词强调SQL质量
    """
    print("\n测试3: 系统提示词强调质量")
    
    agent = SQLGeneratorAgent()
    prompt = agent._create_system_prompt()
    
    # 检查是否强调质量和安全性
    quality_keywords = [
        "确保",
        "正确性",
        "安全性",
        "不再有验证",
        "直接执行"
    ]
    
    found_keywords = []
    for keyword in quality_keywords:
        if keyword in prompt:
            found_keywords.append(keyword)
    
    if len(found_keywords) >= 3:
        print(f"  ✅ 通过: 系统提示词强调质量（找到{len(found_keywords)}个关键词）")
        print(f"  关键词: {found_keywords}")
        return True
    else:
        print(f"  ❌ 失败: 系统提示词未充分强调质量（只找到{len(found_keywords)}个关键词）")
        return False


def test_agent_initialization():
    """
    测试代理正确初始化
    """
    print("\n测试4: 代理初始化")
    
    try:
        agent = SQLGeneratorAgent()
        
        checks = []
        
        # 检查name
        if agent.name == "sql_generator_agent":
            checks.append("name正确")
        else:
            print(f"  ⚠️  name不正确: {agent.name}")
        
        # 检查llm
        if agent.llm is not None:
            checks.append("llm已初始化")
        else:
            print(f"  ⚠️  llm未初始化")
        
        # 检查tools
        if len(agent.tools) >= 2:
            checks.append(f"tools已配置({len(agent.tools)}个)")
        else:
            print(f"  ⚠️  tools数量不足: {len(agent.tools)}")
        
        # 检查agent
        if agent.agent is not None:
            checks.append("agent已创建")
        else:
            print(f"  ⚠️  agent未创建")
        
        if len(checks) >= 3:
            print(f"  ✅ 通过: 代理初始化正常")
            print(f"  检查项: {checks}")
            return True
        else:
            print(f"  ❌ 失败: 部分初始化失败")
            return False
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False


async def main():
    print("=" * 60)
    print("SQLGeneratorAgent简化流程测试")
    print("=" * 60)
    
    tests = [
        test_next_stage_is_execution,
        test_no_validation_stage,
        test_system_prompt_emphasizes_quality,
        test_agent_initialization
    ]
    
    results = []
    for test in tests:
        try:
            if asyncio.iscoroutinefunction(test):
                result = await test()
            else:
                result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    print("=" * 60)
    
    if all(results):
        print("✅ 所有测试通过!")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
