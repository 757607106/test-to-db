"""
通过 HTTP API 测试 Text-to-SQL 功能
"""
import requests
import json
import time

BASE_URL = "http://localhost:2024"


def print_header(text):
    """打印测试标题"""
    print(f"\n{'='*80}")
    print(f"{text}")
    print(f"{'='*80}\n")


def print_success(text):
    """打印成功消息"""
    print(f"✅ {text}")


def print_error(text):
    """打印错误消息"""
    print(f"❌ {text}")


def print_info(text, indent=0):
    """打印信息"""
    prefix = "   " * indent
    print(f"{prefix}{text}")


def create_thread():
    """创建新线程"""
    try:
        response = requests.post(f"{BASE_URL}/threads", json={})
        response.raise_for_status()
        data = response.json()
        thread_id = data.get("thread_id")
        print_info(f"线程创建成功: {thread_id}")
        return thread_id
    except Exception as e:
        print_error(f"创建线程失败: {str(e)}")
        return None


def send_query(thread_id, query, connection_id=7):
    """发送查询"""
    try:
        payload = {
            "assistant_id": "sql_agent",
            "input": {
                "messages": [{"role": "user", "content": query}],
                "connection_id": connection_id
            }
        }
        
        print_info(f"发送查询: '{query}'")
        print_info(f"connection_id: {connection_id}")
        
        response = requests.post(
            f"{BASE_URL}/threads/{thread_id}/runs/stream",
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        # 收集所有事件
        events = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        events.append(data)
                    except json.JSONDecodeError:
                        pass
        
        return events
        
    except Exception as e:
        print_error(f"发送查询失败: {str(e)}")
        return None


def get_thread_state(thread_id):
    """获取线程最终状态"""
    try:
        response = requests.get(f"{BASE_URL}/threads/{thread_id}/state")
        response.raise_for_status()
        data = response.json()
        return data.get("values", {})
    except Exception as e:
        print_error(f"获取状态失败: {str(e)}")
        return None


def test_simple_query():
    """测试 1: 简单查询（快速模式）"""
    print_header("测试 1: 简单查询（快速模式）")
    
    # 创建线程
    thread_id = create_thread()
    if not thread_id:
        return False
    
    # 发送查询
    events = send_query(thread_id, "查询产品数量", connection_id=7)
    if not events:
        return False
    
    print_info(f"收到 {len(events)} 个事件")
    
    # 等待完成
    time.sleep(2)
    
    # 获取最终状态
    state = get_thread_state(thread_id)
    if not state:
        return False
    
    # 验证结果
    print_info("\n验证结果:")
    
    checks = []
    
    # 检查 fast_mode
    fast_mode = state.get("fast_mode")
    print_info(f"fast_mode: {fast_mode}", 1)
    if fast_mode:
        print_success("快速模式已启用")
        checks.append(True)
    else:
        print_error("快速模式未启用")
        checks.append(False)
    
    # 检查 current_stage
    current_stage = state.get("current_stage")
    print_info(f"current_stage: {current_stage}", 1)
    if current_stage == "completed":
        print_success("流程已完成")
        checks.append(True)
    else:
        print_error(f"流程未完成: {current_stage}")
        checks.append(False)
    
    # 检查 generated_sql
    generated_sql = state.get("generated_sql")
    if generated_sql:
        print_success("SQL 已生成")
        print_info(f"SQL: {generated_sql[:100]}...", 1)
        checks.append(True)
    else:
        print_error("SQL 未生成")
        checks.append(False)
    
    # 检查 execution_result
    execution_result = state.get("execution_result")
    if execution_result:
        print_success("SQL 已执行")
        if isinstance(execution_result, dict):
            success = execution_result.get("success")
            print_info(f"执行成功: {success}", 1)
        checks.append(True)
    else:
        print_error("SQL 未执行")
        checks.append(False)
    
    # 总结
    print(f"\n{'='*80}")
    if all(checks):
        print_success("测试通过")
        return True
    else:
        print_error(f"测试失败 ({sum(checks)}/{len(checks)} 通过)")
        return False


def test_complex_query():
    """测试 2: 复杂查询（完整模式）"""
    print_header("测试 2: 复杂查询（完整模式）")
    
    # 创建线程
    thread_id = create_thread()
    if not thread_id:
        return False
    
    # 发送查询
    events = send_query(thread_id, "分析最近的库存分布情况", connection_id=7)
    if not events:
        return False
    
    print_info(f"收到 {len(events)} 个事件")
    
    # 等待完成
    time.sleep(3)
    
    # 获取最终状态
    state = get_thread_state(thread_id)
    if not state:
        return False
    
    # 验证结果
    print_info("\n验证结果:")
    
    checks = []
    
    # 检查 fast_mode
    fast_mode = state.get("fast_mode")
    print_info(f"fast_mode: {fast_mode}", 1)
    if fast_mode == False:
        print_success("完整模式已启用")
        checks.append(True)
    else:
        print_warning("应该使用完整模式")
        checks.append(False)
    
    # 检查 current_stage
    current_stage = state.get("current_stage")
    print_info(f"current_stage: {current_stage}", 1)
    if current_stage == "completed":
        print_success("流程已完成")
        checks.append(True)
    else:
        print_error(f"流程未完成: {current_stage}")
        checks.append(False)
    
    # 检查分析内容
    messages = state.get("messages", [])
    analysis_found = False
    for msg in messages:
        if isinstance(msg, dict) and msg.get("type") == "ai":
            content = msg.get("content", "")
            if len(content) > 100:
                analysis_found = True
                break
    
    if analysis_found:
        print_success("包含详细分析")
        checks.append(True)
    else:
        print_error("缺少详细分析")
        checks.append(False)
    
    # 总结
    print(f"\n{'='*80}")
    if all(checks):
        print_success("测试通过")
        return True
    else:
        print_error(f"测试失败 ({sum(checks)}/{len(checks)} 通过)")
        return False


def test_schema_info():
    """测试 3: Schema 信息传递"""
    print_header("测试 3: Schema 信息传递")
    
    # 创建线程
    thread_id = create_thread()
    if not thread_id:
        return False
    
    # 发送查询
    events = send_query(thread_id, "查询产品名称", connection_id=7)
    if not events:
        return False
    
    # 等待完成
    time.sleep(2)
    
    # 获取最终状态
    state = get_thread_state(thread_id)
    if not state:
        return False
    
    # 验证结果
    print_info("\n验证结果:")
    
    checks = []
    
    # 检查 schema_info
    schema_info = state.get("schema_info")
    if schema_info:
        print_success("schema_info 存在")
        tables = schema_info.get("tables", {})
        print_info(f"tables 数量: {len(tables)}", 1)
        checks.append(True)
    else:
        print_error("schema_info 不存在")
        checks.append(False)
    
    # 检查 SQL 是否包含正确表名
    generated_sql = state.get("generated_sql", "")
    if "inventory" in generated_sql.lower() or "product" in generated_sql.lower():
        print_success("SQL 包含正确表名")
        checks.append(True)
    else:
        print_error("SQL 缺少正确表名")
        checks.append(False)
    
    # 总结
    print(f"\n{'='*80}")
    if all(checks):
        print_success("测试通过")
        return True
    else:
        print_error(f"测试失败 ({sum(checks)}/{len(checks)} 通过)")
        return False


def print_warning(text):
    """打印警告"""
    print(f"⚠️  {text}")


def run_all_tests():
    """运行所有测试"""
    print(f"\n{'='*80}")
    print("Text-to-SQL HTTP API 测试")
    print(f"{'='*80}\n")
    
    print_info(f"测试服务器: {BASE_URL}")
    
    # 测试连接
    try:
        response = requests.get(f"{BASE_URL}/ok", timeout=5)
        response.raise_for_status()
        print_success("服务器连接正常\n")
    except Exception as e:
        print_error(f"服务器连接失败: {str(e)}")
        return 1
    
    tests = [
        ("简单查询（快速模式）", test_simple_query),
        ("复杂查询（完整模式）", test_complex_query),
        ("Schema 信息传递", test_schema_info),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"{name} - 异常: {str(e)}")
            results.append((name, False))
        
        # 测试之间等待
        time.sleep(2)
    
    # 打印总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print(f"\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = run_all_tests()
    sys.exit(exit_code)
