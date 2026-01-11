
import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { DatabaseOutlined, TableOutlined, ColumnHeightOutlined, LinkOutlined } from '@ant-design/icons';

// 表节点组件
export const TableNode = ({ data, isConnectable }: NodeProps) => {
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ 
        type: "spring", 
        stiffness: 260, 
        damping: 20,
        delay: Math.random() * 0.5 
      }}
      whileHover={{ 
        scale: 1.05,
        transition: { duration: 0.2 }
      }}
      className="table-node-cool"
      style={{
        padding: '12px 16px',
        minWidth: '150px',
        textAlign: 'center',
        position: 'relative',
        cursor: 'pointer'
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        style={{ background: '#1890ff' }}
      />
      
      <motion.div
        initial={{ y: 10, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <motion.span
          className="node-icon"
          animate={{ 
            rotate: [0, 5, -5, 0],
            scale: [1, 1.1, 1]
          }}
          transition={{ 
            duration: 2,
            repeat: Infinity,
            repeatType: "reverse"
          }}
        >
          <DatabaseOutlined />
        </motion.span>
        <span style={{ fontWeight: 'bold', fontSize: '14px' }}>
          {data.label || 'Table'}
        </span>
      </motion.div>
      
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        style={{ background: '#1890ff' }}
      />
    </motion.div>
  );
};

// 列节点组件
export const ColumnNode = ({ data, isConnectable }: NodeProps) => {
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0, rotate: -180 }}
      animate={{ scale: 1, opacity: 1, rotate: 0 }}
      transition={{ 
        type: "spring", 
        stiffness: 200, 
        damping: 15,
        delay: Math.random() * 0.7 
      }}
      whileHover={{ 
        scale: 1.08,
        rotate: [0, 2, -2, 0],
        transition: { duration: 0.3 }
      }}
      className="column-node-cool"
      style={{
        padding: '10px 14px',
        minWidth: '120px',
        textAlign: 'center',
        position: 'relative',
        cursor: 'pointer'
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        style={{ background: '#f5576c' }}
      />
      
      <motion.div
        initial={{ x: -10, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <motion.span
          className="node-icon"
          animate={{ 
            y: [0, -2, 0],
            scale: [1, 1.05, 1]
          }}
          transition={{ 
            duration: 1.5,
            repeat: Infinity,
            repeatType: "reverse"
          }}
        >
          <ColumnHeightOutlined />
        </motion.span>
        <span style={{ fontWeight: '500', fontSize: '13px' }}>
          {data.label || 'Column'}
        </span>
      </motion.div>
      
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        style={{ background: '#f5576c' }}
      />
    </motion.div>
  );
};

// 关系节点组件
export const RelationNode = ({ data, isConnectable }: NodeProps) => {
  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ 
        type: "spring", 
        stiffness: 300, 
        damping: 25,
        delay: Math.random() * 0.3 
      }}
      whileHover={{ 
        scale: 1.1,
        boxShadow: "0 8px 25px rgba(79, 172, 254, 0.5)",
        transition: { duration: 0.2 }
      }}
      className="relation-node-cool"
      style={{
        padding: '8px 12px',
        minWidth: '100px',
        textAlign: 'center',
        position: 'relative',
        cursor: 'pointer'
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        style={{ background: '#00f2fe' }}
      />
      
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.4, type: "spring" }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <motion.span
          className="node-icon"
          animate={{ 
            rotate: [0, 360],
            scale: [1, 1.2, 1]
          }}
          transition={{ 
            duration: 3,
            repeat: Infinity,
            ease: "linear"
          }}
        >
          <LinkOutlined />
        </motion.span>
        <span style={{ fontWeight: '500', fontSize: '12px' }}>
          {data.label || 'Relation'}
        </span>
      </motion.div>
      
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        style={{ background: '#00f2fe' }}
      />
    </motion.div>
  );
};

// 默认增强节点组件
export const EnhancedDefaultNode = ({ data, isConnectable }: NodeProps) => {
  const nodeType = data.nodeType || data.type || 'default';
  
  // 根据节点类型选择不同的渐变色
  const getGradient = (type: string) => {
    switch (type.toLowerCase()) {
      case 'table':
        return 'linear-gradient(135deg, #3b82f6 0%, #1e40af 100%)';
      case 'column':
        return 'linear-gradient(135deg, #ec4899 0%, #be185d 100%)';
      case 'relation':
        return 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)';
      default:
        return 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
    }
  };

  const getIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'table':
        return <DatabaseOutlined />;
      case 'column':
        return <ColumnHeightOutlined />;
      case 'relation':
        return <LinkOutlined />;
      default:
        return <TableOutlined />;
    }
  };

  return (
    <motion.div
      initial={{ scale: 0, opacity: 0, y: 20 }}
      animate={{ scale: 1, opacity: 1, y: 0 }}
      transition={{ 
        type: "spring", 
        stiffness: 200, 
        damping: 20,
        delay: Math.random() * 0.5 
      }}
      whileHover={{ 
        scale: 1.05,
        y: -2,
        transition: { duration: 0.2 }
      }}
      style={{
        background: getGradient(nodeType),
        border: '2px solid rgba(255, 255, 255, 0.2)',
        borderRadius: '12px',
        padding: '12px 16px',
        minWidth: '140px',
        textAlign: 'center',
        color: 'white',
        fontWeight: '600',
        textShadow: '0 1px 2px rgba(0, 0, 0, 0.3)',
        position: 'relative',
        overflow: 'hidden',
        cursor: 'pointer',
        boxShadow: '0 4px 15px rgba(0, 0, 0, 0.2)'
      }}
      className="graph-node"
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
      />
      
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
      >
        <motion.span
          animate={{ 
            rotate: [0, 5, -5, 0],
            scale: [1, 1.1, 1]
          }}
          transition={{ 
            duration: 2,
            repeat: Infinity,
            repeatType: "reverse"
          }}
          style={{ fontSize: '16px' }}
        >
          {getIcon(nodeType)}
        </motion.span>
        <span style={{ fontSize: '14px' }}>
          {data.label || 'Node'}
        </span>
      </motion.div>
      
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
      />
    </motion.div>
  );
};

// 节点类型映射
export const nodeTypes = {
  table: TableNode,
  column: ColumnNode,
  relation: RelationNode,
  enhanced: EnhancedDefaultNode,
  default: EnhancedDefaultNode
};

