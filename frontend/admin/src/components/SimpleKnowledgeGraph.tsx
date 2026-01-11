
import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Button,
  Select,
  Switch,
  Space,
  Tooltip,
  Input,
  Spin,
  Empty
} from 'antd';
import {
  ExpandOutlined,
  ReloadOutlined,
  FullscreenOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  DatabaseOutlined,
  EyeInvisibleOutlined,
  EyeOutlined
} from '@ant-design/icons';
import '../styles/KnowledgeGraph.css';

// 导出GraphData接口供其他组件使用
export interface GraphData {
  nodes: any[];
  edges: any[];
}

const { Option } = Select;
const { Search } = Input;

interface SimpleKnowledgeGraphProps {
  data: GraphData;
  loading?: boolean;
  width?: number;
  height?: number;
  onNodeClick?: (node: any) => void;
  onEdgeClick?: (edge: any) => void;
  onNodeDoubleClick?: (node: any) => void;
}

const SimpleKnowledgeGraph: React.FC<SimpleKnowledgeGraphProps> = ({
  data,
  loading = false,
  width = 1200,
  height = 700,
  onNodeClick,
  onEdgeClick,
  onNodeDoubleClick
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 状态管理
  const [layout, setLayout] = useState('force');
  const [showLabels, setShowLabels] = useState(true);
  const [enableAnimation, setEnableAnimation] = useState(true);
  const [nodeSize, setNodeSize] = useState('medium');
  const [searchValue, setSearchValue] = useState('');
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [showControls, setShowControls] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [dragNode, setDragNode] = useState<any>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [nodesWithPositions, setNodesWithPositions] = useState<any[]>([]);

  // 统计信息
  const stats = {
    totalNodes: data.nodes.length,
    totalEdges: data.edges.length,
    tableNodes: data.nodes.filter(n => (n.type || n.nodeType || '').toLowerCase().includes('table')).length,
    columnNodes: data.nodes.filter(n => (n.type || n.nodeType || '').toLowerCase().includes('column')).length,
    relationNodes: data.nodes.filter(n => (n.type || n.nodeType || '').toLowerCase().includes('relation')).length
  };

  // 节点位置计算
  const calculateNodePositions = useCallback((nodes: any[], layoutType: string, preservePositions = false) => {
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 3;

    return nodes.map((node, index) => {
      // 如果节点已有位置且要保持位置，则使用现有位置
      if (preservePositions && node.x !== undefined && node.y !== undefined) {
        return { ...node };
      }

      let x, y;

      switch (layoutType) {
        case 'circular':
          const angle = (index / nodes.length) * 2 * Math.PI;
          x = centerX + radius * Math.cos(angle);
          y = centerY + radius * Math.sin(angle);
          break;
        case 'grid':
          const cols = Math.ceil(Math.sqrt(nodes.length));
          const cellWidth = width / cols;
          const cellHeight = height / Math.ceil(nodes.length / cols);
          x = (index % cols) * cellWidth + cellWidth / 2;
          y = Math.floor(index / cols) * cellHeight + cellHeight / 2;
          break;
        case 'force':
        default:
          // 简单的力导向布局模拟
          x = centerX + (Math.random() - 0.5) * radius * 1.5;
          y = centerY + (Math.random() - 0.5) * radius * 1.5;
          break;
      }

      return {
        ...node,
        x,
        y
      };
    });
  }, [width, height]);

  // 获取节点样式
  const getNodeStyle = (node: any) => {
    const baseSize = nodeSize === 'small' ? 20 : nodeSize === 'large' ? 40 : 30;
    const nodeType = (node.nodeType || node.type || 'default').toLowerCase();
    
    const styles = {
      table: {
        color: '#1890ff',
        size: baseSize + 10,
        icon: '🗃️'
      },
      column: {
        color: '#eb2f96',
        size: baseSize,
        icon: '📋'
      },
      relation: {
        color: '#13c2c2',
        size: baseSize + 5,
        icon: '🔗'
      },
      default: {
        color: '#52c41a',
        size: baseSize,
        icon: '⚪'
      }
    };

    return styles[nodeType as keyof typeof styles] || styles.default;
  };

  // 绘制图形
  const drawGraph = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 设置变换
    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(zoom, zoom);

    // 使用当前节点位置或重新计算
    let currentNodes = nodesWithPositions;
    if (currentNodes.length === 0 || currentNodes.length !== data.nodes.length) {
      currentNodes = calculateNodePositions(data.nodes, layout, false);
      setNodesWithPositions(currentNodes);
    }

    // 绘制边
    data.edges.forEach(edge => {
      const sourceNode = currentNodes.find(n => n.id === edge.source);
      const targetNode = currentNodes.find(n => n.id === edge.target);

      if (sourceNode && targetNode) {
        ctx.beginPath();
        ctx.moveTo(sourceNode.x, sourceNode.y);
        ctx.lineTo(targetNode.x, targetNode.y);
        ctx.strokeStyle = '#91d5ff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // 绘制箭头
        const angle = Math.atan2(targetNode.y - sourceNode.y, targetNode.x - sourceNode.x);
        const arrowLength = 10;
        const arrowAngle = Math.PI / 6;

        ctx.beginPath();
        ctx.moveTo(targetNode.x, targetNode.y);
        ctx.lineTo(
          targetNode.x - arrowLength * Math.cos(angle - arrowAngle),
          targetNode.y - arrowLength * Math.sin(angle - arrowAngle)
        );
        ctx.moveTo(targetNode.x, targetNode.y);
        ctx.lineTo(
          targetNode.x - arrowLength * Math.cos(angle + arrowAngle),
          targetNode.y - arrowLength * Math.sin(angle + arrowAngle)
        );
        ctx.stroke();
      }
    });

    // 绘制节点
    currentNodes.forEach(node => {
      const style = getNodeStyle(node);
      const isSelected = selectedNodes.includes(node.id);
      const isDraggedNode = dragNode && dragNode.id === node.id;

      // 绘制节点圆圈
      ctx.beginPath();
      ctx.arc(node.x, node.y, style.size, 0, 2 * Math.PI);
      ctx.fillStyle = isDraggedNode ? '#40a9ff' : style.color;
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#ff4d4f' : '#ffffff';
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.stroke();

      // 绘制图标
      ctx.font = `${style.size / 2}px Arial`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(style.icon, node.x, node.y);

      // 绘制标签
      if (showLabels) {
        const label = node.label || node.id;
        ctx.font = '12px Arial';
        ctx.fillStyle = '#333';
        ctx.fillText(label, node.x, node.y + style.size + 15);
      }
    });

    ctx.restore();
  }, [data, layout, showLabels, nodeSize, selectedNodes, dragNode, zoom, offset, width, height, nodesWithPositions, calculateNodePositions]);

  // 搜索功能
  const handleSearch = (value: string) => {
    setSearchValue(value);
    if (!value.trim()) {
      setSelectedNodes([]);
      return;
    }

    const matchedNodes = data.nodes
      .filter(node => {
        const label = node.label || node.id || '';
        return label.toLowerCase().includes(value.toLowerCase());
      })
      .map(node => node.id);

    setSelectedNodes(matchedNodes);
  };

  // 控制函数
  const handleZoomIn = () => setZoom(prev => Math.min(prev * 1.2, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev * 0.8, 0.1));
  const handleFitView = () => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  };
  const handleRefresh = () => drawGraph();
  
  const handleFullscreen = () => {
    if (containerRef.current) {
      if (!isFullscreen) {
        containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        document.exitFullscreen();
        setIsFullscreen(false);
      }
    }
  };

  // 获取鼠标在画布上的坐标
  const getMousePos = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left - offset.x) / zoom,
      y: (event.clientY - rect.top - offset.y) / zoom
    };
  };

  // 查找鼠标位置的节点
  const findNodeAtPosition = (x: number, y: number) => {
    return nodesWithPositions.find(node => {
      const style = getNodeStyle(node);
      const distance = Math.sqrt((x - node.x) ** 2 + (y - node.y) ** 2);
      return distance <= style.size;
    });
  };

  // 鼠标按下事件
  const handleMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const mousePos = getMousePos(event);
    const clickedNode = findNodeAtPosition(mousePos.x, mousePos.y);

    if (clickedNode) {
      setIsDragging(true);
      setDragNode(clickedNode);
      setDragOffset({
        x: mousePos.x - clickedNode.x,
        y: mousePos.y - clickedNode.y
      });
    }
  };

  // 鼠标移动事件
  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging || !dragNode) return;

    event.preventDefault();
    const mousePos = getMousePos(event);
    const newX = mousePos.x - dragOffset.x;
    const newY = mousePos.y - dragOffset.y;

    // 更新节点位置
    const updatedNodes = nodesWithPositions.map(node =>
      node.id === dragNode.id ? { ...node, x: newX, y: newY } : node
    );
    setNodesWithPositions(updatedNodes);

    // 立即重绘
    drawGraph();
  };

  // 鼠标释放事件
  const handleMouseUp = () => {
    setIsDragging(false);
    setDragNode(null);
    setDragOffset({ x: 0, y: 0 });
  };

  // 画布点击事件
  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDragging) return; // 如果正在拖拽，不处理点击

    const mousePos = getMousePos(event);
    const clickedNode = findNodeAtPosition(mousePos.x, mousePos.y);

    if (clickedNode && onNodeClick) {
      onNodeClick(clickedNode);
    }
  };

  // 画布双击事件
  const handleCanvasDoubleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const mousePos = getMousePos(event);
    const clickedNode = findNodeAtPosition(mousePos.x, mousePos.y);

    if (clickedNode && onNodeDoubleClick) {
      onNodeDoubleClick(clickedNode);
    }
  };

  // 滚轮缩放事件
  const handleWheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // 计算缩放因子
    const scaleFactor = event.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(3, zoom * scaleFactor));

    // 计算新的偏移量，使缩放以鼠标位置为中心
    const newOffsetX = mouseX - (mouseX - offset.x) * (newZoom / zoom);
    const newOffsetY = mouseY - (mouseY - offset.y) * (newZoom / zoom);

    setZoom(newZoom);
    setOffset({ x: newOffsetX, y: newOffsetY });
  };

  // 初始化节点位置
  useEffect(() => {
    if (!loading && data.nodes.length > 0) {
      // 只有在节点数据变化时才重新计算位置
      if (nodesWithPositions.length !== data.nodes.length) {
        const newNodes = calculateNodePositions(data.nodes, layout, false);
        setNodesWithPositions(newNodes);
      }
    }
  }, [data.nodes, loading, calculateNodePositions, layout, nodesWithPositions.length]);

  // 重绘图形
  useEffect(() => {
    if (!loading && data.nodes.length > 0) {
      drawGraph();
    }
  }, [drawGraph, loading, data.nodes.length]);

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      // 触发重新绘制
      setTimeout(() => {
        if (!loading && data.nodes.length > 0) {
          drawGraph();
        }
      }, 100);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawGraph, loading, data.nodes.length]);

  // 渲染空状态
  if (!loading && (!data.nodes || data.nodes.length === 0)) {
    return (
      <div className="knowledge-graph-container" style={{ height }}>
        <div className="kg-empty">
          <DatabaseOutlined className="kg-empty-icon" />
          <div className="kg-empty-text">暂无图数据</div>
          <div className="kg-empty-description">请选择数据库连接并同步数据</div>
        </div>
      </div>
    );
  }

  return (
    <div className="knowledge-graph-container" style={{
      height,
      width: '100%',
      position: 'relative',
      overflow: 'hidden'
    }} ref={containerRef}>
      {/* 加载状态 */}
      {loading && (
        <div className="kg-loading">
          <Spin size="large" tip="加载知识图谱中..." />
        </div>
      )}

      {/* 顶部控制栏 */}
      <div className="kg-top-controls kg-fade-in" style={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        right: '10px',
        zIndex: 10,
        background: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(8px)',
        borderRadius: '8px',
        padding: '12px',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
        display: showControls ? 'block' : 'none'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          {/* 左侧控制 */}
          <Space size="middle">
            <Search
              placeholder="搜索节点..."
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onSearch={handleSearch}
              style={{ width: 200 }}
              allowClear
              size="small"
            />

            <Space>
              <span style={{ fontSize: '12px', color: '#666' }}>布局:</span>
              <Select
                value={layout}
                onChange={(value) => {
                  setLayout(value);
                  // 重新计算布局时不保持位置
                  const newNodes = calculateNodePositions(data.nodes, value, false);
                  setNodesWithPositions(newNodes);
                }}
                size="small"
                style={{ width: 100 }}
              >
                <Option value="force">力导向</Option>
                <Option value="circular">环形</Option>
                <Option value="grid">网格</Option>
              </Select>
            </Space>

            <Space>
              <span style={{ fontSize: '12px', color: '#666' }}>大小:</span>
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
            </Space>

            <Space>
              <span style={{ fontSize: '12px', color: '#666' }}>标签:</span>
              <Switch
                checked={showLabels}
                onChange={setShowLabels}
                size="small"
              />
            </Space>
          </Space>

          {/* 右侧控制 */}
          <Space>
            <Tooltip title="隐藏控制面板">
              <Button
                size="small"
                icon={<EyeInvisibleOutlined />}
                onClick={() => setShowControls(false)}
              />
            </Tooltip>
          </Space>
        </div>
      </div>

      {/* 显示控制面板按钮 */}
      {!showControls && (
        <div style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          zIndex: 10
        }}>
          <Tooltip title="显示控制面板">
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => setShowControls(true)}
              style={{
                background: 'rgba(255, 255, 255, 0.9)',
                backdropFilter: 'blur(8px)'
              }}
            />
          </Tooltip>
        </div>
      )}

      {/* 工具栏 */}
      <div className="kg-toolbar kg-scale-in">
        <Tooltip title="放大" placement="left">
          <Button size="small" icon={<ZoomInOutlined />} onClick={handleZoomIn} />
        </Tooltip>
        <Tooltip title="缩小" placement="left">
          <Button size="small" icon={<ZoomOutOutlined />} onClick={handleZoomOut} />
        </Tooltip>
        <Tooltip title="适应画布" placement="left">
          <Button size="small" icon={<ExpandOutlined />} onClick={handleFitView} />
        </Tooltip>
        <Tooltip title="刷新" placement="left">
          <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} />
        </Tooltip>
        <Tooltip title="全屏" placement="left">
          <Button size="small" icon={<FullscreenOutlined />} onClick={handleFullscreen} />
        </Tooltip>
      </div>

      {/* 图例 */}
      <div className="kg-legend kg-fade-in">
        <div className="kg-legend-title">节点类型</div>
        <div className="kg-legend-item">
          <div className="kg-legend-color" style={{ background: '#1890ff' }}></div>
          <span>表 ({stats.tableNodes})</span>
        </div>
        <div className="kg-legend-item">
          <div className="kg-legend-color" style={{ background: '#eb2f96' }}></div>
          <span>列 ({stats.columnNodes})</span>
        </div>
        <div className="kg-legend-item">
          <div className="kg-legend-color" style={{ background: '#13c2c2' }}></div>
          <span>关系 ({stats.relationNodes})</span>
        </div>
      </div>

      {/* 统计信息 */}
      <div className="kg-stats kg-fade-in">
        <div className="kg-stats-item">
          <span className="kg-stats-label">节点:</span>
          <span className="kg-stats-value">{stats.totalNodes}</span>
        </div>
        <div className="kg-stats-item">
          <span className="kg-stats-label">边:</span>
          <span className="kg-stats-value">{stats.totalEdges}</span>
        </div>
        {selectedNodes.length > 0 && (
          <div className="kg-stats-item">
            <span className="kg-stats-label">匹配:</span>
            <span className="kg-stats-value">{selectedNodes.length}</span>
          </div>
        )}
        <div className="kg-stats-item">
          <span className="kg-stats-label">缩放:</span>
          <span className="kg-stats-value">{Math.round(zoom * 100)}%</span>
        </div>
      </div>

      {/* 画布 */}
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onClick={handleCanvasClick}
        onDoubleClick={handleCanvasDoubleClick}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{
          width: '100%',
          height: '100%',
          background: 'linear-gradient(135deg, #f6f9fc 0%, #ffffff 100%)',
          borderRadius: '8px',
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
      />
    </div>
  );
};

export default SimpleKnowledgeGraph;
