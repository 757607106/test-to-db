import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ToolCallBox, ToolCalls } from '../tool-calls';
import { AIMessage, ToolMessage } from '@langchain/langgraph-sdk';

/**
 * 工具调用显示组件的单元测试
 * 
 * 这些测试验证工具调用的显示功能，包括：
 * 1. ToolCallBox 在不同状态下的渲染
 * 2. 图像提取功能
 * 3. 工具结果匹配逻辑
 * 4. 状态图标选择
 */

describe('ToolCallBox Component', () => {
  describe('基本渲染', () => {
    test('应该渲染工具名称', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: { query: 'test' },
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      expect(screen.getByText('search_database')).toBeInTheDocument();
    });

    test('应该显示完成状态图标（当有结果时）', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: {},
        type: 'tool_call',
      };

      const toolResult: ToolMessage = {
        type: 'tool',
        content: 'Search results',
        tool_call_id: 'tool-1',
        id: 'result-1',
      };

      const { container } = render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

      // 检查是否有绿色的完成图标
      const checkIcon = container.querySelector('.text-green-500');
      expect(checkIcon).toBeInTheDocument();
    });

    test('应该显示待处理状态图标（当没有结果时）', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: {},
        type: 'tool_call',
      };

      const { container } = render(<ToolCallBox toolCall={toolCall} />);

      // 检查是否有蓝色的待处理图标（带动画）
      const loaderIcon = container.querySelector('.text-blue-500.animate-spin');
      expect(loaderIcon).toBeInTheDocument();
    });

    test('应该显示错误状态图标（当结果包含错误时）', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: {},
        type: 'tool_call',
      };

      const toolResult: ToolMessage = {
        type: 'tool',
        content: JSON.stringify({ error: 'Database connection failed' }),
        tool_call_id: 'tool-1',
        id: 'result-1',
      };

      const { container } = render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

      // 检查是否有红色的错误图标
      const errorIcon = container.querySelector('.text-red-500');
      expect(errorIcon).toBeInTheDocument();
    });
  });

  describe('展开/折叠功能', () => {
    test('应该默认折叠', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: { query: 'test' },
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      // ARGUMENTS 标题不应该显示（因为是折叠状态）
      expect(screen.queryByText('ARGUMENTS')).not.toBeInTheDocument();
    });

    test('应该在点击后展开', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: { query: 'test' },
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      // 点击工具名称按钮
      fireEvent.click(screen.getByText('search_database'));

      // ARGUMENTS 标题应该显示
      expect(screen.getByText('ARGUMENTS')).toBeInTheDocument();
    });

    test('应该在展开时显示参数', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: { query: 'test query', limit: 10 },
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      fireEvent.click(screen.getByText('search_database'));

      // 检查参数是否以 JSON 格式显示
      expect(screen.getByText(/"query": "test query"/)).toBeInTheDocument();
      expect(screen.getByText(/"limit": 10/)).toBeInTheDocument();
    });

    test('应该在展开时显示结果', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'search_database',
        args: {},
        type: 'tool_call',
      };

      const toolResult: ToolMessage = {
        type: 'tool',
        content: 'Found 5 results',
        tool_call_id: 'tool-1',
        id: 'result-1',
      };

      render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

      fireEvent.click(screen.getByText('search_database'));

      expect(screen.getByText('RESULT')).toBeInTheDocument();
      expect(screen.getByText('Found 5 results')).toBeInTheDocument();
    });
  });

  describe('特殊工具类型', () => {
    test('应该将 handoff 工具标记为已完成（即使没有结果）', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'transfer_to_analyst',
        args: {},
        type: 'tool_call',
      };

      const { container } = render(<ToolCallBox toolCall={toolCall} />);

      // Handoff 工具应该显示完成图标，而不是待处理图标
      const checkIcon = container.querySelector('.text-green-500');
      expect(checkIcon).toBeInTheDocument();
    });

    test('应该处理未知工具名称', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: '',
        args: {},
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      expect(screen.getByText('Unknown Tool')).toBeInTheDocument();
    });
  });

  describe('内容处理', () => {
    test('应该处理 JSON 字符串结果', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'get_data',
        args: {},
        type: 'tool_call',
      };

      const toolResult: ToolMessage = {
        type: 'tool',
        content: JSON.stringify({ status: 'success', data: [1, 2, 3] }),
        tool_call_id: 'tool-1',
        id: 'result-1',
      };

      render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

      fireEvent.click(screen.getByText('get_data'));

      expect(screen.getByText(/"status": "success"/)).toBeInTheDocument();
      expect(screen.getByText(/"data": \[/)).toBeInTheDocument();
    });

    test('应该处理对象类型的结果', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'get_data',
        args: {},
        type: 'tool_call',
      };

      const toolResult: ToolMessage = {
        type: 'tool',
        content: { status: 'success', count: 42 } as any,
        tool_call_id: 'tool-1',
        id: 'result-1',
      };

      render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

      fireEvent.click(screen.getByText('get_data'));

      expect(screen.getByText(/"status": "success"/)).toBeInTheDocument();
      expect(screen.getByText(/"count": 42/)).toBeInTheDocument();
    });

    test('应该处理空参数', () => {
      const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
        id: 'tool-1',
        name: 'simple_tool',
        args: {},
        type: 'tool_call',
      };

      render(<ToolCallBox toolCall={toolCall} />);

      fireEvent.click(screen.getByText('simple_tool'));

      // 空参数应该显示为空对象
      expect(screen.getByText('ARGUMENTS')).toBeInTheDocument();
      expect(screen.getByText('{}')).toBeInTheDocument();
    });
  });
});

describe('ToolCalls Component', () => {
  describe('基本渲染', () => {
    test('应该渲染多个工具调用', () => {
      const toolCalls: AIMessage['tool_calls'] = [
        { id: 'tool-1', name: 'search', args: {}, type: 'tool_call' },
        { id: 'tool-2', name: 'calculate', args: {}, type: 'tool_call' },
        { id: 'tool-3', name: 'format', args: {}, type: 'tool_call' },
      ];

      render(<ToolCalls toolCalls={toolCalls} />);

      expect(screen.getByText('search')).toBeInTheDocument();
      expect(screen.getByText('calculate')).toBeInTheDocument();
      expect(screen.getByText('format')).toBeInTheDocument();
    });

    test('应该过滤掉无效的工具调用', () => {
      const toolCalls: AIMessage['tool_calls'] = [
        { id: 'tool-1', name: 'valid_tool', args: {}, type: 'tool_call' },
        { id: 'tool-2', name: '', args: {}, type: 'tool_call' }, // 无效：空名称
        { id: 'tool-3', name: '   ', args: {}, type: 'tool_call' }, // 无效：只有空格
      ];

      render(<ToolCalls toolCalls={toolCalls} />);

      expect(screen.getByText('valid_tool')).toBeInTheDocument();
      expect(screen.queryByText('Unknown Tool')).not.toBeInTheDocument();
    });

    test('应该在没有工具调用时不渲染任何内容', () => {
      const { container } = render(<ToolCalls toolCalls={[]} />);

      expect(container.firstChild).toBeNull();
    });

    test('应该在工具调用为 null 或 undefined 时不渲染', () => {
      const { container: container1 } = render(<ToolCalls toolCalls={null as any} />);
      const { container: container2 } = render(<ToolCalls toolCalls={undefined as any} />);

      expect(container1.firstChild).toBeNull();
      expect(container2.firstChild).toBeNull();
    });
  });

  describe('工具结果匹配', () => {
    test('应该通过 tool_call_id 匹配工具结果', () => {
      const toolCalls: AIMessage['tool_calls'] = [
        { id: 'tool-1', name: 'search', args: {}, type: 'tool_call' },
        { id: 'tool-2', name: 'calculate', args: {}, type: 'tool_call' },
      ];

      const toolResults: ToolMessage[] = [
        {
          type: 'tool',
          content: 'Search results',
          tool_call_id: 'tool-1',
          id: 'result-1',
        },
        {
          type: 'tool',
          content: 'Calculation results',
          tool_call_id: 'tool-2',
          id: 'result-2',
        },
      ];

      render(<ToolCalls toolCalls={toolCalls} toolResults={toolResults} />);

      // 展开第一个工具
      fireEvent.click(screen.getByText('search'));
      expect(screen.getByText('Search results')).toBeInTheDocument();

      // 展开第二个工具
      fireEvent.click(screen.getByText('calculate'));
      expect(screen.getByText('Calculation results')).toBeInTheDocument();
    });

    test('应该处理没有匹配结果的工具调用', () => {
      const toolCalls: AIMessage['tool_calls'] = [
        { id: 'tool-1', name: 'search', args: {}, type: 'tool_call' },
        { id: 'tool-2', name: 'calculate', args: {}, type: 'tool_call' },
      ];

      const toolResults: ToolMessage[] = [
        {
          type: 'tool',
          content: 'Search results',
          tool_call_id: 'tool-1',
          id: 'result-1',
        },
        // tool-2 没有结果
      ];

      const { container } = render(<ToolCalls toolCalls={toolCalls} toolResults={toolResults} />);

      // 第一个工具应该显示完成图标
      const checkIcons = container.querySelectorAll('.text-green-500');
      expect(checkIcons.length).toBeGreaterThan(0);

      // 第二个工具应该显示待处理图标
      const loaderIcons = container.querySelectorAll('.text-blue-500.animate-spin');
      expect(loaderIcons.length).toBeGreaterThan(0);
    });

    test('应该处理结果顺序与调用顺序不同的情况', () => {
      const toolCalls: AIMessage['tool_calls'] = [
        { id: 'tool-1', name: 'first', args: {}, type: 'tool_call' },
        { id: 'tool-2', name: 'second', args: {}, type: 'tool_call' },
        { id: 'tool-3', name: 'third', args: {}, type: 'tool_call' },
      ];

      const toolResults: ToolMessage[] = [
        {
          type: 'tool',
          content: 'Result 3',
          tool_call_id: 'tool-3',
          id: 'result-3',
        },
        {
          type: 'tool',
          content: 'Result 1',
          tool_call_id: 'tool-1',
          id: 'result-1',
        },
        {
          type: 'tool',
          content: 'Result 2',
          tool_call_id: 'tool-2',
          id: 'result-2',
        },
      ];

      render(<ToolCalls toolCalls={toolCalls} toolResults={toolResults} />);

      // 展开并验证每个工具都有正确的结果
      fireEvent.click(screen.getByText('first'));
      expect(screen.getByText('Result 1')).toBeInTheDocument();

      fireEvent.click(screen.getByText('second'));
      expect(screen.getByText('Result 2')).toBeInTheDocument();

      fireEvent.click(screen.getByText('third'));
      expect(screen.getByText('Result 3')).toBeInTheDocument();
    });
  });
});

describe('图像提取功能', () => {
  // 注意：由于图像提取是内部函数，我们通过集成测试来验证
  // 这里我们测试包含图像的工具结果是否正确渲染

  test('应该从 base64 data URL 中提取图像', () => {
    const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
      id: 'tool-1',
      name: 'generate_chart',
      args: {},
      type: 'tool_call',
    };

    const toolResult: ToolMessage = {
      type: 'tool',
      content: 'Chart generated: data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      tool_call_id: 'tool-1',
      id: 'result-1',
    };

    const { container } = render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

    fireEvent.click(screen.getByText('generate_chart'));

    // 检查是否有 img 标签
    const images = container.querySelectorAll('img');
    expect(images.length).toBeGreaterThan(0);
  });

  test('应该从 HTTP URL 中提取图像', () => {
    const toolCall: NonNullable<AIMessage['tool_calls']>[0] = {
      id: 'tool-1',
      name: 'fetch_image',
      args: {},
      type: 'tool_call',
    };

    const toolResult: ToolMessage = {
      type: 'tool',
      content: 'Image URL: https://example.com/image.png',
      tool_call_id: 'tool-1',
      id: 'result-1',
    };

    const { container } = render(<ToolCallBox toolCall={toolCall} toolResult={toolResult} />);

    fireEvent.click(screen.getByText('fetch_image'));

    // 检查是否有 img 标签
    const images = container.querySelectorAll('img');
    expect(images.length).toBeGreaterThan(0);
  });
});
