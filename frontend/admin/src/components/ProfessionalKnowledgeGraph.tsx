
import React, { useEffect, useRef, useState } from 'react';
import { Graph } from '@antv/g6';
import { Card, Space, Select, Switch, Input, Button, Tooltip, Spin, Badge } from 'antd';
import {
  SearchOutlined,
  ExpandOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  ReloadOutlined,
  SettingOutlined,
  FullscreenOutlined,
  FullscreenExitOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';

const { Option } = Select;

interface ProfessionalKnowledgeGraphProps {
  data: {
    nodes: any[];
    edges: any[];
  };
  loading?: boolean;
  width?: number;
  height?: number;
  onNodeClick?: (node: any) => void;
  onEdgeClick?: (edge: any) => void;
  onNodeDoubleClick?: (node: any) => void;
}

const ProfessionalKnowledgeGraph: React.FC<ProfessionalKnowledgeGraphProps> = ({
  data,
  loading = false,
  width = 1200,
  height = 700,
  onNodeClick,
  onEdgeClick,
  onNodeDoubleClick
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  
  // 状态管理
  const [layout, setLayout] = useState('force');
  const [showLabels, setShowLabels] = useState(true);
  const [nodeSize, setNodeSize] = useState('medium');
  const [searchValue, setSearchValue] = useState('');
  const [showControls, setShowControls] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showLegend, setShowLegend] = useState(true);

  // 这些函数在 G6 v5 中不再需要，因为样式直接在配置中定义

  // 初始化图谱
  useEffect(() => {
    if (!containerRef.current || loading || !data.nodes.length) return;

    // 清理之前的图谱
    if (graphRef.current && typeof graphRef.current.destroy === 'function') {
      try {
        graphRef.current.destroy();
      } catch (error) {
        console.warn('Error destroying previous graph:', error);
      }
      graphRef.current = null;
    }

    // 处理数据 - 转换为 G6 v5 格式，并确保边ID唯一和节点存在
    const edgeIdSet = new Set<string>();
    let edgeIdCounter = 0;

    // 首先处理节点
    const processedNodes = data.nodes.map(node => ({
      id: node.id,
      data: {
        label: node.label || node.id,
        nodeType: node.data?.nodeType || node.type || 'default',
        cluster: node.data?.nodeType || node.type || 'default',
        ...node.data
      }
    }));

    // 创建节点ID集合用于验证边
    const nodeIdSet = new Set(processedNodes.map(node => node.id));
    console.log('可用节点ID:', Array.from(nodeIdSet));

    // 处理边，验证源节点和目标节点是否存在
    const validEdges: any[] = [];
    const invalidEdges: any[] = [];

    data.edges.forEach(edge => {
      // 检查源节点和目标节点是否存在
      if (!nodeIdSet.has(edge.source)) {
        console.warn(`边 ${edge.id} 的源节点 ${edge.source} 不存在`);
        invalidEdges.push(edge);
        return;
      }

      if (!nodeIdSet.has(edge.target)) {
        console.warn(`边 ${edge.id} 的目标节点 ${edge.target} 不存在`);
        invalidEdges.push(edge);
        return;
      }

      let edgeId = edge.id || `${edge.source}-${edge.target}`;

      // 确保边ID唯一，如果重复则添加后缀
      if (edgeIdSet.has(edgeId)) {
        edgeIdCounter++;
        edgeId = `${edgeId}-${edgeIdCounter}`;
        console.warn(`发现重复边ID，已重命名为: ${edgeId}`);
      }
      edgeIdSet.add(edgeId);

      validEdges.push({
        id: edgeId,
        source: edge.source,
        target: edge.target,
        data: {
          label: edge.label || '',
          ...edge.data
        }
      });
    });

    if (invalidEdges.length > 0) {
      console.warn(`跳过了 ${invalidEdges.length} 个无效边:`, invalidEdges);
    }

    const processedData = {
      nodes: processedNodes,
      edges: validEdges
    };

    // 创建图谱实例 - 使用正确的 G6 v5 API，并添加错误处理
    let graph;
    try {
      console.log('创建图谱实例，数据:', {
        nodes: processedData.nodes.length,
        edges: processedData.edges.length,
        edgeIds: processedData.edges.map(e => e.id)
      });

      graph = new Graph({
        container: containerRef.current,
        width,
        height,
        data: processedData,
        node: {
          palette: {
            type: 'group',
            field: 'cluster',
            color: ['#1890ff', '#eb2f96', '#13c2c2', '#52c41a', '#faad14', '#f5222d']
          },
          style: {
            size: nodeSize === 'small' ? 20 : nodeSize === 'large' ? 40 : 30,
            labelText: (d: any) => showLabels ? d.data.label : '',
            labelPosition: 'bottom',
            labelFontSize: 12,
            labelFill: '#333',
            stroke: '#ffffff',
            lineWidth: 2
          }
        },
        edge: {
          style: {
            stroke: '#999',
            lineWidth: 2,
            endArrow: true,
            labelText: (d: any) => showLabels ? d.data.label || '' : '',
            labelFill: '#666',
            labelFontSize: 10
          }
        },
        layout: {
          type: layout === 'force' ? 'force' : layout === 'circular' ? 'circular' : layout === 'grid' ? 'grid' : 'dagre',
          ...(layout === 'force' && {
            preventOverlap: true,
            nodeSize: 50,
            linkDistance: 150
          }),
          ...(layout === 'circular' && {
            radius: 200
          }),
          ...(layout === 'grid' && {
            rows: Math.ceil(Math.sqrt(data.nodes.length)),
            cols: Math.ceil(Math.sqrt(data.nodes.length))
          })
        },
        behaviors: [
          'drag-canvas',
          'zoom-canvas',
          {
            type: 'drag-element',
            key: 'drag-element',
            enable: (event: any) => ['node', 'combo'].includes(event.targetType),
            animation: true,
            dropEffect: 'move',
            shadow: false
          }
        ]
      });

      console.log('图谱实例创建成功');
    } catch (error) {
      console.error('创建图谱实例失败:', error);
      // 如果创建失败，返回空的清理函数
      return () => {};
    }

    // 事件监听
    graph.on('node:click', (evt: any) => {
      onNodeClick?.(evt.target.id);
    });

    graph.on('node:dblclick', (evt: any) => {
      onNodeDoubleClick?.(evt.target.id);
    });

    graph.on('edge:click', (evt: any) => {
      onEdgeClick?.(evt.target.id);
    });

    // 拖拽事件监听 - 添加拖拽反馈效果
    graph.on('node:dragstart', (evt: any) => {
      const { target } = evt;
      console.log('开始拖拽节点:', target.id, target.data);

      // 如果是表节点，可以添加特殊的视觉效果
      if (target && target.data && target.data.nodeType === 'table') {
        console.log('开始拖拽表节点:', target.id);
        // 未来可以在这里添加表节点拖拽时的特殊效果
      }
    });

    graph.on('node:drag', (evt: any) => {
      const { target } = evt;
      // 拖拽过程中的实时反馈
      if (target && target.data && target.data.nodeType === 'table') {
        // 未来可以在这里实现表节点带动子节点的效果
        console.log('正在拖拽表节点:', target.id);
      }
    });

    graph.on('node:dragend', (evt: any) => {
      const { target } = evt;
      console.log('结束拖拽节点:', target.id);

      // 拖拽结束后的处理
      if (target && target.data && target.data.nodeType === 'table') {
        console.log('表节点拖拽完成:', target.id);
        // 未来可以在这里添加拖拽完成后的处理逻辑
      }
    });

    // 渲染图谱
    try {
      console.log('开始渲染图谱...');
      graph.render();
      console.log('图谱渲染成功');
      graphRef.current = graph;
    } catch (error) {
      console.error('图谱渲染失败:', error);
      // 如果渲染失败，尝试清理图谱实例
      if (graph && typeof graph.destroy === 'function') {
        try {
          graph.destroy();
        } catch (destroyError) {
          console.warn('清理失败的图谱实例时出错:', destroyError);
        }
      }
      return () => {};
    }

    return () => {
      if (graphRef.current && typeof graphRef.current.destroy === 'function') {
        try {
          graphRef.current.destroy();
        } catch (error) {
          console.warn('Error destroying graph:', error);
        }
        graphRef.current = null;
      }
    };
  }, [data, layout, nodeSize, showLabels, width, height, loading]);

  // 搜索功能 - 简化版本，G6 v5 的高亮功能需要不同的实现方式
  const handleSearch = (value: string) => {
    setSearchValue(value);
    if (!graphRef.current) return;

    if (!value.trim()) {
      // 重新渲染以清除高亮
      graphRef.current.render();
      return;
    }

    // 查找匹配的节点
    const matchedNodes = data.nodes.filter(node =>
      node.label?.toLowerCase().includes(value.toLowerCase()) ||
      node.id.toLowerCase().includes(value.toLowerCase())
    );

    // 在 G6 v5 中，我们可以通过重新设置数据来实现高亮效果
    // 这里简化处理，实际项目中可以使用插件或自定义渲染
    console.log('匹配的节点:', matchedNodes.map(n => n.label || n.id));
  };

  // 工具栏操作 - 使用 G6 v5 API
  const handleZoomIn = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom * 1.2);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.getZoom();
      graphRef.current.zoomTo(currentZoom * 0.8);
    }
  };

  const handleFitView = () => {
    graphRef.current?.fitView();
  };

  const handleRefresh = () => {
    graphRef.current?.render();
  };

  // 全屏功能
  const handleFullscreen = () => {
    if (!isFullscreen) {
      // 进入全屏
      const element = document.documentElement;
      if (element.requestFullscreen) {
        element.requestFullscreen();
      }
    } else {
      // 退出全屏
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  };

  // 监听全屏状态变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  if (loading) {
    return (
      <div style={{ 
        height, 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f6f9fc 0%, #ffffff 100%)',
        borderRadius: '8px',
        gap: '16px'
      }}>
        <Spin size="large" />
        <div style={{ color: '#1890ff' }}>加载专业知识图谱中...</div>
      </div>
    );
  }

  if (!data.nodes || data.nodes.length === 0) {
    return (
      <div style={{ 
        height, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #f6f9fc 0%, #ffffff 100%)',
        borderRadius: '8px',
        flexDirection: 'column'
      }}>
        <SettingOutlined style={{ fontSize: '48px', color: '#ccc', marginBottom: '16px' }} />
        <div style={{ fontSize: '16px', color: '#666' }}>暂无图数据</div>
        <div style={{ fontSize: '14px', color: '#999', marginTop: '8px' }}>请选择数据库连接并同步数据</div>
      </div>
    );
  }

  return (
    <div style={{ 
      position: 'relative', 
      width: '100%', 
      height,
      background: 'linear-gradient(135deg, #f6f9fc 0%, #ffffff 100%)',
      borderRadius: '8px',
      overflow: 'hidden'
    }}>
      {/* 顶部控制栏 */}
      {showControls && (
        <Card 
          size="small" 
          style={{ 
            position: 'absolute', 
            top: 10, 
            left: 10, 
            right: 10, 
            zIndex: 10,
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(8px)'
          }}
        >
          <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space wrap>
              <Input
                placeholder="搜索节点..."
                prefix={<SearchOutlined />}
                value={searchValue}
                onChange={(e) => handleSearch(e.target.value)}
                style={{ width: 200 }}
                size="small"
              />
              
              <Select
                value={layout}
                onChange={setLayout}
                size="small"
                style={{ width: 120 }}
              >
                <Option value="force">力导向</Option>
                <Option value="circular">环形</Option>
                <Option value="grid">网格</Option>
                <Option value="dagre">层次</Option>
              </Select>

              <Select
                value={nodeSize}
                onChange={setNodeSize}
                size="small"
                style={{ width: 80 }}
              >
                <Option value="small">小</Option>
                <Option value="medium">中</Option>
                <Option value="large">大</Option>
              </Select>

              <Space>
                <span style={{ fontSize: '12px', color: '#666' }}>标签:</span>
                <Switch
                  checked={showLabels}
                  onChange={setShowLabels}
                  size="small"
                />
              </Space>
            </Space>

            <Space>
              <Tooltip title="放大">
                <Button size="small" icon={<ZoomInOutlined />} onClick={handleZoomIn} />
              </Tooltip>
              <Tooltip title="缩小">
                <Button size="small" icon={<ZoomOutOutlined />} onClick={handleZoomOut} />
              </Tooltip>
              <Tooltip title="适应画布">
                <Button size="small" icon={<ExpandOutlined />} onClick={handleFitView} />
              </Tooltip>
              <Tooltip title="刷新布局">
                <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} />
              </Tooltip>
              <Tooltip title={isFullscreen ? "退出全屏" : "全屏显示"}>
                <Button
                  size="small"
                  icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                  onClick={handleFullscreen}
                />
              </Tooltip>
              <Tooltip title={showLegend ? "隐藏图例" : "显示图例"}>
                <Button
                  size="small"
                  icon={showLegend ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={() => setShowLegend(!showLegend)}
                />
              </Tooltip>
              <Tooltip title="隐藏控制面板">
                <Button
                  size="small"
                  icon={<SettingOutlined />}
                  onClick={() => setShowControls(false)}
                />
              </Tooltip>
            </Space>
          </Space>
        </Card>
      )}

      {/* 显示控制面板按钮 */}
      {!showControls && (
        <Button
          type="primary"
          size="small"
          icon={<SettingOutlined />}
          onClick={() => setShowControls(true)}
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            zIndex: 10
          }}
        />
      )}

      {/* 图谱容器 */}
      <div 
        ref={containerRef} 
        style={{ 
          width: '100%', 
          height: '100%',
          background: 'transparent'
        }} 
      />

      {/* 图例 */}
      {showLegend && (
        <Card
          size="small"
          title="图例"
          style={{
            position: 'absolute',
            bottom: 10,
            right: 10,
            width: 200,
            zIndex: 10,
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(8px)'
          }}
        >
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: '#1890ff',
                border: '2px solid #ffffff'
              }} />
              <span style={{ fontSize: '12px' }}>表 (Table)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                backgroundColor: '#eb2f96',
                border: '2px solid #ffffff'
              }} />
              <span style={{ fontSize: '12px' }}>列 (Column)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '16px',
                height: '2px',
                backgroundColor: '#999',
                position: 'relative'
              }}>
                <div style={{
                  position: 'absolute',
                  right: '-4px',
                  top: '-3px',
                  width: '0',
                  height: '0',
                  borderLeft: '4px solid #999',
                  borderTop: '3px solid transparent',
                  borderBottom: '3px solid transparent'
                }} />
              </div>
              <span style={{ fontSize: '12px' }}>关系 (Relation)</span>
            </div>
            <div style={{
              borderTop: '1px solid #f0f0f0',
              paddingTop: '8px',
              marginTop: '8px',
              fontSize: '11px',
              color: '#999'
            }}>
              节点: {data.nodes.length} | 边: {data.edges.length}
            </div>
          </Space>
        </Card>
      )}

      {/* 简化的底部信息栏（当图例隐藏时显示） */}
      {!showLegend && (
        <div style={{
          position: 'absolute',
          bottom: 10,
          right: 10,
          background: 'rgba(255, 255, 255, 0.9)',
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#666'
        }}>
          节点: {data.nodes.length} | 边: {data.edges.length}
        </div>
      )}
    </div>
  );
};

export default ProfessionalKnowledgeGraph;
