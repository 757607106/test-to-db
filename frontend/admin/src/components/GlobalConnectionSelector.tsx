import React from 'react';
import { Select, Spin } from 'antd';
import { DatabaseOutlined } from '@ant-design/icons';
import { useGlobalConnection } from '../contexts/GlobalConnectionContext';
import '../styles/GlobalConnectionSelector.css';

const { Option } = Select;

interface GlobalConnectionSelectorProps {
  // Props kept for compatibility but will be ignored in favor of context
  selectedConnectionId?: number | null;
  setSelectedConnectionId?: (id: number | null) => void;
}

const GlobalConnectionSelector: React.FC<GlobalConnectionSelectorProps> = () => {
  const { connections, selectedConnectionId, setSelectedConnectionId, loading } = useGlobalConnection();

  return (
    <div className="global-connection-selector">
      <Select
        placeholder="选择数据库连接"
        value={selectedConnectionId || undefined}
        onChange={(value) => setSelectedConnectionId(value ? Number(value) : null)}
        loading={loading}
        style={{ width: 220 }}
        popupMatchSelectWidth={false}
        suffixIcon={loading ? <Spin size="small" /> : <DatabaseOutlined />}
        className="connection-select"
      >
        {connections.map(conn => (
          <Option key={conn.id} value={conn.id}>
            {conn.name} {conn.type ? `(${conn.type})` : ''}
          </Option>
        ))}
      </Select>
    </div>
  );
};

export default GlobalConnectionSelector;
