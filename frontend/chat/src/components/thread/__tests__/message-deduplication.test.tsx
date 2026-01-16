import { renderHook } from '@testing-library/react';
import { useMemo } from 'react';
import { Message } from '@langchain/langgraph-sdk';

/**
 * 消息去重逻辑的单元测试
 * 
 * 这些测试验证 Thread 组件中的消息去重功能，确保：
 * 1. 重复的消息被正确去重
 * 2. 保留最新版本的消息
 * 3. 没有 ID 的消息被正确处理
 */

// 模拟 Thread 组件中的去重逻辑
function useMessageDeduplication(rawMessages: Message[]) {
  return useMemo(() => {
    const seenMessageIds = new Set<string>();
    const deduped: typeof rawMessages = [];
    
    // 从后向前遍历，保留最新版本的消息
    for (let i = rawMessages.length - 1; i >= 0; i--) {
      const msg = rawMessages[i];
      
      if (msg.id) {
        if (!seenMessageIds.has(msg.id)) {
          seenMessageIds.add(msg.id);
          deduped.unshift(msg);
        }
      } else {
        // 没有 id 的消息直接保留
        deduped.unshift(msg);
      }
    }
    
    return deduped;
  }, [rawMessages]);
}

describe('Message Deduplication', () => {
  describe('基本去重功能', () => {
    test('应该去除具有相同 ID 的重复消息', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'First version' },
        { id: 'msg-1', type: 'human', content: 'Second version' },
        { id: 'msg-2', type: 'ai', content: 'Another message' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(2);
      expect(result.current[0].id).toBe('msg-1');
      expect(result.current[1].id).toBe('msg-2');
    });

    test('应该保留没有重复的消息', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'Message 1' },
        { id: 'msg-2', type: 'ai', content: 'Message 2' },
        { id: 'msg-3', type: 'human', content: 'Message 3' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(3);
      expect(result.current.map(m => m.id)).toEqual(['msg-1', 'msg-2', 'msg-3']);
    });

    test('应该处理空消息数组', () => {
      const rawMessages: Message[] = [];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(0);
    });
  });

  describe('保留最新版本', () => {
    test('应该保留最后出现的消息版本', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'First version' },
        { id: 'msg-1', type: 'human', content: 'Second version' },
        { id: 'msg-1', type: 'human', content: 'Third version (latest)' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(1);
      expect(result.current[0].content).toBe('Third version (latest)');
    });

    test('应该在多个重复消息中保留每个 ID 的最新版本', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'msg-1 v1' },
        { id: 'msg-2', type: 'ai', content: 'msg-2 v1' },
        { id: 'msg-1', type: 'human', content: 'msg-1 v2 (latest)' },
        { id: 'msg-3', type: 'human', content: 'msg-3 v1' },
        { id: 'msg-2', type: 'ai', content: 'msg-2 v2 (latest)' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(3);
      expect(result.current[0].content).toBe('msg-1 v2 (latest)');
      expect(result.current[1].content).toBe('msg-2 v2 (latest)');
      expect(result.current[2].content).toBe('msg-3 v1');
    });

    test('应该保持消息的原始顺序（基于第一次出现）', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'First' },
        { id: 'msg-2', type: 'ai', content: 'Second' },
        { id: 'msg-3', type: 'human', content: 'Third' },
        { id: 'msg-1', type: 'human', content: 'First (updated)' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(3);
      expect(result.current.map(m => m.id)).toEqual(['msg-1', 'msg-2', 'msg-3']);
      expect(result.current[0].content).toBe('First (updated)');
    });
  });

  describe('处理没有 ID 的消息', () => {
    test('应该保留所有没有 ID 的消息', () => {
      const rawMessages: Message[] = [
        { type: 'human', content: 'Message without ID 1' } as Message,
        { type: 'ai', content: 'Message without ID 2' } as Message,
        { type: 'human', content: 'Message without ID 3' } as Message,
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(3);
      expect(result.current[0].content).toBe('Message without ID 1');
      expect(result.current[1].content).toBe('Message without ID 2');
      expect(result.current[2].content).toBe('Message without ID 3');
    });

    test('应该同时处理有 ID 和没有 ID 的消息', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'With ID' },
        { type: 'ai', content: 'Without ID 1' } as Message,
        { id: 'msg-2', type: 'human', content: 'With ID 2' },
        { type: 'ai', content: 'Without ID 2' } as Message,
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(4);
      expect(result.current[0].id).toBe('msg-1');
      expect(result.current[1].id).toBeUndefined();
      expect(result.current[2].id).toBe('msg-2');
      expect(result.current[3].id).toBeUndefined();
    });

    test('应该保留没有 ID 的重复内容消息', () => {
      const rawMessages: Message[] = [
        { type: 'human', content: 'Same content' } as Message,
        { type: 'human', content: 'Same content' } as Message,
        { type: 'human', content: 'Same content' } as Message,
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      // 没有 ID 的消息不应该被去重
      expect(result.current).toHaveLength(3);
    });
  });

  describe('边界情况', () => {
    test('应该处理只有一条消息的情况', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'Only message' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(1);
      expect(result.current[0].id).toBe('msg-1');
    });

    test('应该处理所有消息都是重复的情况', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'v1' },
        { id: 'msg-1', type: 'human', content: 'v2' },
        { id: 'msg-1', type: 'human', content: 'v3' },
        { id: 'msg-1', type: 'human', content: 'v4 (latest)' },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(1);
      expect(result.current[0].content).toBe('v4 (latest)');
    });

    test('应该处理包含工具消息的复杂场景', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'User question' },
        { id: 'msg-2', type: 'ai', content: 'AI response', tool_calls: [{ id: 'tool-1', name: 'search', args: {} }] },
        { id: 'msg-3', type: 'tool', content: 'Tool result', tool_call_id: 'tool-1' },
        { id: 'msg-2', type: 'ai', content: 'AI response (updated)', tool_calls: [{ id: 'tool-1', name: 'search', args: {} }] },
      ];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      expect(result.current).toHaveLength(3);
      expect(result.current[0].id).toBe('msg-1');
      expect(result.current[1].id).toBe('msg-2');
      expect(result.current[1].content).toBe('AI response (updated)');
      expect(result.current[2].id).toBe('msg-3');
    });
  });

  describe('性能和稳定性', () => {
    test('应该处理大量消息', () => {
      const rawMessages: Message[] = Array.from({ length: 1000 }, (_, i) => ({
        id: `msg-${i % 100}`, // 创建一些重复
        type: i % 2 === 0 ? 'human' : 'ai',
        content: `Message ${i}`,
      })) as Message[];

      const { result } = renderHook(() => useMessageDeduplication(rawMessages));

      // 应该只保留 100 个唯一的消息（0-99）
      expect(result.current).toHaveLength(100);
    });

    test('应该在输入不变时返回相同的引用（memoization）', () => {
      const rawMessages: Message[] = [
        { id: 'msg-1', type: 'human', content: 'Message 1' },
        { id: 'msg-2', type: 'ai', content: 'Message 2' },
      ];

      const { result, rerender } = renderHook(
        ({ messages }) => useMessageDeduplication(messages),
        { initialProps: { messages: rawMessages } }
      );

      const firstResult = result.current;
      
      // 使用相同的输入重新渲染
      rerender({ messages: rawMessages });
      
      // 应该返回相同的引用（由于 useMemo）
      expect(result.current).toBe(firstResult);
    });
  });
});
