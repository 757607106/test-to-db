import React, { useState, useEffect } from 'react';
import { Select, Button, message, Typography, Space, Card } from 'antd';
import { DatabaseOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import ProfessionalKnowledgeGraph from '../components/ProfessionalKnowledgeGraph';
import { useGlobalConnection } from '../contexts/GlobalConnectionContext';

import * as api from '../services/api';

const { Title } = Typography;
const { Option } = Select;

// 图数据接口
interface GraphData {
  nodes: any[];
  edges: any[];
}

// 知识图谱可视化组件
const KnowledgeGraphVisualization = () => {
  // 状态管理
  const { selectedConnectionId } = useGlobalConnection();
  // Keep local connections state only if needed for other purposes, otherwise remove
  // const [connections, setConnections] = useState<any[]>([]); 
  const [loading, setLoading] = useState<boolean>(false);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });

  // 监听全局连接变化
  useEffect(() => {
    if (selectedConnectionId) {
      fetchGraphData(selectedConnectionId);
    } else {
      setGraphData({ nodes: [], edges: [] });
    }
  }, [selectedConnectionId]);

  /* Removed fetchConnections and handleConnectionChange as they are handled globally */


  // 获取图数据
  const fetchGraphData = async (connectionId: number) => {
    setLoading(true);
    try {
      const response = await api.getGraphVisualization(connectionId);
      console.log('收到图数据:', response.data);
      
      if (!response.data || !response.data.nodes || response.data.nodes.length === 0) {
        message.info('没有找到图数据');
        setGraphData({ nodes: [], edges: [] });
        setLoading(false);
        return;
      }

      // 处理节点和边，确保能显示
      const processedData = processGraphData(response.data);
      
      // 设置图数据
      setGraphData({
        nodes: processedData.nodes,
        edges: processedData.edges
      });
      
      message.success(`已加载图数据: ${processedData.nodes.length} 个节点, ${processedData.edges.length} 个边`);
      
    } catch (error) {
      console.error('加载图数据失败:', error);
      message.error('加载图数据失败');
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  };

  // 知识图谱数据处理器
  const processGraphData = (data: GraphData) => {
    // 处理节点数据
    const nodes = data.nodes.map((node, index) => {
      // 确定节点类型
      const nodeType = node.type || (node.data && node.data.nodeType) || 'default';
      
      return {
        id: node.id || `node-${index}`,
        label: (node.data && node.data.label) || node.label || `Node ${index + 1}`,
        type: nodeType,
        nodeType: nodeType,
        ...node.data,
        ...node
      };
    });

    // 处理边数据
    const edges = data.edges.map((edge, index) => {
      return {
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.label || '',
        type: edge.type || 'default',
        ...edge
      };
    });

    return { nodes, edges };
  };

  // 刷新图数据
  const refreshGraph = () => {
    if (selectedConnectionId) {
      fetchGraphData(selectedConnectionId);
    }
  };

  // 发现并同步数据
  const discoverAndSync = async () => {
    if (!selectedConnectionId) return;
    
    setLoading(true);
    try {
      await api.discoverAndSyncSchema(selectedConnectionId);
      message.success('架构发现和同步完成');
      // 重新获取图数据
      fetchGraphData(selectedConnectionId);
    } catch (error) {
      console.error('同步失败:', error);
      message.error('架构同步失败');
      setLoading(false);
    }
  };



  // 节点点击处理
  const handleNodeClick = (node: any) => {
    console.log('节点点击:', node);
    message.info(`点击了节点: ${node.label || node.id}`);
  };

  // 边点击处理
  const handleEdgeClick = (edge: any) => {
    console.log('边点击:', edge);
    message.info(`点击了边: ${edge.label || edge.id}`);
  };

  // 节点双击处理
  const handleNodeDoubleClick = (node: any) => {
    console.log('节点双击:', node);
    message.info(`双击了节点: ${node.label || node.id}`);
  };

  return (
    <div style={{ padding: '24px', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/*<Title level={3} style={{ marginBottom: '24px', color: '#1890ff' }}>*/}
      {/*  🧠 知识图谱可视化*/}
      {/*</Title>*/}

      {/* 控制面板 */}
      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <Space size="large">
            {/* Connection Selector Removed */}
            {/*
            <Space>
              <DatabaseOutlined style={{ color: '#1890ff' }} />
              <Select
                placeholder="选择数据库连接"
                style={{ width: 240 }}
                onChange={handleConnectionChange}
                loading={loading}
              >
                {connections.map(conn => (
                  <Option key={conn.id} value={conn.id}>{conn.name}</Option>
                ))}
              </Select>
            </Space>
            */}

            <Button
              icon={<ReloadOutlined />}
              onClick={refreshGraph}
              disabled={!selectedConnectionId}
              loading={loading}
            >
              刷新数据
            </Button>

            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={discoverAndSync}
              disabled={!selectedConnectionId}
              loading={loading}
            >
              发现并同步
            </Button>
          </Space>
          

        </div>
      </Card>
      
      {/* 知识图谱可视化区域 */}
      <div style={{
        flex: 1,
        minHeight: '600px',
        height: 'calc(100vh - 200px)', // 确保铺满剩余空间
        width: '100%'
      }}>
        <ProfessionalKnowledgeGraph
          data={graphData}
          loading={loading}
          width={window.innerWidth - 48} // 动态宽度
          height={window.innerHeight - 200} // 动态高度
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
        />
      </div>
    </div>
  );
};

// 外部包装组件
const GraphVisualizationPage = () => {
  return <KnowledgeGraphVisualization />;
};

export default GraphVisualizationPage;
