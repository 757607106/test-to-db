
import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
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
import '../styles/ProfessionalKnowledgeGraph.css';

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

  // 使用 useMemo 缓存处理后的数据，避免每次都重新计算
  const processedData = useMemo(() => {
    if (!data.nodes || data.nodes.length === 0) {
      return { nodes: [], edges: [] };
    }

    // 性能优化：如果节点数量过多，限制显示数量
    const maxNodes = 500;
    const maxEdges = 1000;
    const shouldLimit = data.nodes.length > maxNodes;
    
    const nodesToProcess = shouldLimit ? data.nodes.slice(0, maxNodes) : data.nodes;
    const edgesToProcess = shouldLimit ? data.edges.slice(0, maxEdges) : data.edges;

    // 首先处理节点
    const processedNodes = nodesToProcess.map(node => ({
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

    // 处理边，验证源节点和目标节点是否存在
    const validEdges: any[] = [];
    const edgeIdSet = new Set<string>();
    let edgeIdCounter = 0;

    edgesToProcess.forEach(edge => {
      // 检查源节点和目标节点是否存在
      if (!nodeIdSet.has(edge.source) || !nodeIdSet.has(edge.target)) {
        return;
      }

      let edgeId = edge.id || `${edge.source}-${edge.target}`;

      // 确保边ID唯一
      if (edgeIdSet.has(edgeId)) {
        edgeIdCounter++;
        edgeId = `${edgeId}-${edgeIdCounter}`;
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

    return {
      nodes: processedNodes,
      edges: validEdges
    };
  }, [data]);

  // 初始化图谱
  useEffect(() => {
    if (!containerRef.current || loading || processedData.nodes.length === 0) return;

    // 清理之前的图谱
    if (graphRef.current && typeof graphRef.current.destroy === 'function') {
      try {
        graphRef.current.destroy();
      } catch (error) {
        console.warn('Error destroying previous graph:', error);
      }
      graphRef.current = null;
    }

    // 创建图谱实例 - 使用正确的 G6 v5 API，并添加错误处理
    let graph;
    try {
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
            size: nodeSize === 'small' ? 25 : nodeSize === 'large' ? 45 : 35,
            labelText: (d: any) => showLabels ? d.data.label : '',
            labelPosition: 'bottom',
            labelFontSize: nodeSize === 'small' ? 10 : nodeSize === 'large' ? 14 : 12,
            labelFill: '#333',
            labelBackground: true,
            labelBackgroundFill: 'rgba(255, 255, 255, 0.8)',
            labelBackgroundRadius: 4,
            labelPadding: [2, 4],
            stroke: '#ffffff',
            lineWidth: 2,
            fillOpacity: 0.85
          }
        },
        edge: {
          style: {
            stroke: '#d9d9d9',
            lineWidth: 1.5,
            endArrow: true,
            labelText: (d: any) => showLabels ? d.data.label || '' : '',
            labelFill: '#666',
            labelFontSize: 10,
            labelBackground: true,
            labelBackgroundFill: 'rgba(255, 255, 255, 0.9)',
            labelPadding: [2, 4],
            opacity: 0.6
          }
        },
        layout: {
          type: layout === 'force' ? 'force' : layout === 'circular' ? 'circular' : layout === 'grid' ? 'grid' : 'dagre',
          ...(layout === 'force' && {
            preventOverlap: true,
            nodeSize: nodeSize === 'small' ? 40 : nodeSize === 'large' ? 80 : 60,
            linkDistance: 200,
            nodeSpacing: 50,
            nodeStrength: -50,
            edgeStrength: 0.6,
            collideStrength: 0.8,
            alpha: 0.3,
            alphaDecay: 0.028,
            alphaMin: 0.01,
            // 性能优化：限制迭代次数，节点越多迭代次数越少
            iterations: Math.max(100, 300 - processedData.nodes.length)
          }),
          ...(layout === 'circular' && {
            radius: Math.max(300, Math.min(processedData.nodes.length * 5, 800)),
            divisions: Math.min(processedData.nodes.length, 10)
          }),
          ...(layout === 'grid' && {
            rows: Math.ceil(Math.sqrt(processedData.nodes.length)),
            cols: Math.ceil(Math.sqrt(processedData.nodes.length)),
            sortBy: 'cluster'
          }),
          ...(layout === 'dagre' && {
            rankdir: 'TB',
            nodesep: 40,
            ranksep: 80,
            controlPoints: true
          })
        },
        behaviors: [
          'drag-canvas',
          'zoom-canvas',
          {
            type: 'drag-element',
            key: 'drag-element',
            enable: (event: any) => ['node', 'combo'].includes(event.targetType),
            // 性能优化：禁用动画和阴影
            animation: false,
            dropEffect: 'move',
            shadow: false
          }
        ]
      });
    } catch (error) {
      console.error('创建图谱实例失败:', error);
      // 如果创建失败，返回空的清理函数
      return () => {};
    }

    // 事件监听 - 使用正确的 G6 v5 事件对象
    graph.on('node:click', (evt: any) => {
      // G6 v5 中，evt.itemId 或 evt.target.id 是节点ID
      const nodeId = evt.itemId || evt.target?.id;
      if (nodeId) {
        const nodeData = processedData.nodes.find(n => n.id === nodeId);
        onNodeClick?.(nodeData || { id: nodeId });
      }
    });

    graph.on('node:dblclick', (evt: any) => {
      const nodeId = evt.itemId || evt.target?.id;
      if (nodeId) {
        const nodeData = processedData.nodes.find(n => n.id === nodeId);
        onNodeDoubleClick?.(nodeData || { id: nodeId });
      }
    });

    graph.on('edge:click', (evt: any) => {
      const edgeId = evt.itemId || evt.target?.id;
      if (edgeId) {
        const edgeData = processedData.edges.find(e => e.id === edgeId);
        onEdgeClick?.(edgeData || { id: edgeId });
      }
    });

    // 渲染图谱
    try {
      graph.render();
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
  }, [processedData, layout, nodeSize, showLabels, width, height]); // 数据、布局、样式、尺寸变化时重建

  // 搜索功能 - 使用 useCallback 优化
  const handleSearch = useCallback((value: string) => {
    setSearchValue(value);
    if (!graphRef.current) return;

    if (!value.trim()) {
      graphRef.current.render();
      return;
    }

    // 查找匹配的节点
    const matchedNodes = data.nodes.filter(node =>
      node.label?.toLowerCase().includes(value.toLowerCase()) ||
      node.id.toLowerCase().includes(value.toLowerCase())
    );

    // 可以在这里实现高亮效果
  }, [data.nodes]);

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
      <div className="pkg-loading-container" style={{ height }}>
        <Spin size="large" />
        <div className="pkg-loading-text">加载专业知识图谱中...</div>
      </div>
    );
  }

  if (!data.nodes || data.nodes.length === 0) {
    return (
      <div className="pkg-empty-container" style={{ height }}>
        <SettingOutlined className="pkg-empty-icon" />
        <div className="pkg-empty-text">暂无图数据</div>
        <div className="pkg-empty-subtext">请选择数据库连接并同步数据</div>
      </div>
    );
  }

  return (
    <div className="pkg-container" style={{ height }}>
      {/* 顶部控制栏 */}
      {showControls && (
        <Card 
          size="small" 
          className="pkg-controls-card"
        >
          <Space wrap className="pkg-controls-wrapper">
            {/* 数据量过大警告 */}
            {data.nodes.length > 500 && (
              <div style={{ 
                padding: '4px 12px', 
                background: '#fff7e6', 
                border: '1px solid #ffd591',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#d46b08'
              }}>
                ⚠️ 节点数量较多（{data.nodes.length}），已限制显示前 500 个节点。建议使用网格或层次布局以获得更好性能。
              </div>
            )}
            <Space wrap>
              <Input
                placeholder="搜索节点..."
                prefix={<SearchOutlined />}
                value={searchValue}
                onChange={(e) => handleSearch(e.target.value)}
                className="pkg-search-input"
                size="small"
              />
              
              <Select
                value={layout}
                onChange={setLayout}
                size="small"
                className="pkg-layout-select"
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
                className="pkg-size-select"
              >
                <Option value="small">小</Option>
                <Option value="medium">中</Option>
                <Option value="large">大</Option>
              </Select>

              <Space>
                <span className="pkg-label-text">标签:</span>
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
          className="pkg-show-controls-btn"
        />
      )}

      {/* 图谱容器 */}
      <div 
        ref={containerRef} 
        className="pkg-graph-canvas"
      />

      {/* 图例 */}
      {showLegend && (
        <Card
          size="small"
          title="图例"
          className="pkg-legend-card"
        >
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <div className="pkg-legend-item">
              <div className="pkg-legend-dot-table" />
              <span className="pkg-legend-text">表 (Table)</span>
            </div>
            <div className="pkg-legend-item">
              <div className="pkg-legend-dot-column" />
              <span className="pkg-legend-text">列 (Column)</span>
            </div>
            <div className="pkg-legend-item">
              <div className="pkg-legend-line-relation">
                <div className="pkg-legend-arrow" />
              </div>
              <span className="pkg-legend-text">关系 (Relation)</span>
            </div>
            <div className="pkg-legend-footer">
              显示: {processedData.nodes.length} 节点 / {processedData.edges.length} 边
              {data.nodes.length > processedData.nodes.length && (
                <span style={{ color: '#d46b08', fontSize: '11px', marginLeft: '8px' }}>
                  (总计 {data.nodes.length} 节点)
                </span>
              )}
            </div>
          </Space>
        </Card>
      )}

      {/* 简化的底部信息栏（当图例隐藏时显示） */}
      {!showLegend && (
        <div className="pkg-simple-footer">
          显示: {processedData.nodes.length} 节点 / {processedData.edges.length} 边
          {data.nodes.length > processedData.nodes.length && (
            <span style={{ color: '#d46b08', marginLeft: '8px' }}>
              (总计 {data.nodes.length} 节点)
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export default ProfessionalKnowledgeGraph;
