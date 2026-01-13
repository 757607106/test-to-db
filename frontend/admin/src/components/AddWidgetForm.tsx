/**
 * AddWidgetForm 组件
 * 用于添加新的Widget到Dashboard
 */
import React, { useState, useEffect } from 'react';
import {
  Form,
  Input,
  Select,
  Button,
  Space,
  Radio,
  message,
  Spin,
  Alert,
} from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { dashboardService, widgetService } from '../services/dashboardService';
import type { WidgetCreate, WidgetQueryConfig } from '../types/dashboard';

const { TextArea } = Input;
const { Option } = Select;

interface AddWidgetFormProps {
  dashboardId: number;
  onSuccess: () => void;
  onCancel: () => void;
}

interface DBConnection {
  id: number;
  name: string;
  db_type: string;
}

export const AddWidgetForm: React.FC<AddWidgetFormProps> = ({
  dashboardId,
  onSuccess,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [queryMode, setQueryMode] = useState<'natural' | 'sql'>('natural');
  const [generatedSQL, setGeneratedSQL] = useState<string>('');
  const [generating, setGenerating] = useState(false);

  // 获取数据库连接列表
  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    setLoadingConnections(true);
    try {
      const response = await fetch('http://localhost:8000/api/connections/');
      const data = await response.json();
      setConnections(data);
    } catch (error) {
      message.error('获取数据库连接失败');
      console.error(error);
    } finally {
      setLoadingConnections(false);
    }
  };

  // 生成SQL（调用后端AI）
  const handleGenerateSQL = async () => {
    const connectionId = form.getFieldValue('connection_id');
    const naturalQuery = form.getFieldValue('natural_query');

    if (!connectionId) {
      message.warning('请先选择数据库连接');
      return;
    }
    if (!naturalQuery?.trim()) {
      message.warning('请输入自然语言查询');
      return;
    }

    setGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/api/query/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_id: connectionId,
          natural_language_query: naturalQuery,
        }),
      });

      const result = await response.json();
      
      if (result.sql) {
        setGeneratedSQL(result.sql);
        form.setFieldsValue({ sql_query: result.sql });
        message.success('SQL生成成功');
      } else {
        message.error(result.error || 'SQL生成失败');
      }
    } catch (error) {
      message.error('生成SQL时出错');
      console.error(error);
    } finally {
      setGenerating(false);
    }
  };

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const sqlQuery = queryMode === 'natural' ? generatedSQL : values.sql_query;
      
      if (!sqlQuery?.trim()) {
        message.error('请生成或输入SQL查询');
        return;
      }

      const queryConfig: WidgetQueryConfig = {
        original_query: queryMode === 'natural' ? values.natural_query : '',
        generated_sql: sqlQuery,
        parameters: {},
      };

      const widgetData: WidgetCreate = {
        widget_type: values.widget_type,
        title: values.title,
        connection_id: values.connection_id,
        query_config: queryConfig,
        chart_config: values.widget_type === 'chart' ? { type: 'bar' } : undefined,
        position_config: { x: 0, y: 0, w: 6, h: 4 },
        refresh_interval: values.refresh_interval || 0,
      };

      await widgetService.createWidget(dashboardId, widgetData);
      message.success('组件添加成功');
      onSuccess();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '添加组件失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Spin spinning={loadingConnections}>
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          widget_type: 'table',
          refresh_interval: 0,
        }}
      >
        <Form.Item
          name="title"
          label="组件标题"
          rules={[{ required: true, message: '请输入组件标题' }]}
        >
          <Input placeholder="例如：销售数据统计" />
        </Form.Item>

        <Form.Item
          name="widget_type"
          label="组件类型"
          rules={[{ required: true, message: '请选择组件类型' }]}
        >
          <Radio.Group>
            <Radio.Button value="table">数据表格</Radio.Button>
            <Radio.Button value="chart">图表</Radio.Button>
          </Radio.Group>
        </Form.Item>

        <Form.Item
          name="connection_id"
          label="数据库连接"
          rules={[{ required: true, message: '请选择数据库连接' }]}
        >
          <Select placeholder="请选择数据库连接">
            {connections.map((conn) => (
              <Option key={conn.id} value={conn.id}>
                {conn.name} ({conn.db_type})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="查询方式">
          <Radio.Group value={queryMode} onChange={(e) => setQueryMode(e.target.value)}>
            <Radio value="natural">自然语言（AI生成SQL）</Radio>
            <Radio value="sql">直接输入SQL</Radio>
          </Radio.Group>
        </Form.Item>

        {queryMode === 'natural' ? (
          <>
            <Form.Item
              name="natural_query"
              label="自然语言查询"
              rules={[{ required: queryMode === 'natural', message: '请输入查询描述' }]}
            >
              <TextArea
                rows={3}
                placeholder="用自然语言描述你的查询，例如：查询最近30天的销售数据，按地区分组统计"
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleGenerateSQL}
                loading={generating}
              >
                生成SQL
              </Button>
            </Form.Item>
            {generatedSQL && (
              <Alert
                message="生成的SQL"
                description={
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                    {generatedSQL}
                  </pre>
                }
                type="success"
                style={{ marginBottom: 16 }}
              />
            )}
          </>
        ) : (
          <Form.Item
            name="sql_query"
            label="SQL查询"
            rules={[{ required: queryMode === 'sql', message: '请输入SQL查询' }]}
          >
            <TextArea
              rows={5}
              placeholder="SELECT * FROM table_name WHERE ..."
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        )}

        <Form.Item
          name="refresh_interval"
          label="自动刷新间隔"
        >
          <Select>
            <Option value={0}>手动刷新</Option>
            <Option value={30}>30秒</Option>
            <Option value={60}>1分钟</Option>
            <Option value={300}>5分钟</Option>
            <Option value={600}>10分钟</Option>
          </Select>
        </Form.Item>

        <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
          <Space>
            <Button onClick={onCancel}>取消</Button>
            <Button
              type="primary"
              onClick={handleSubmit}
              loading={loading}
              disabled={queryMode === 'natural' && !generatedSQL}
            >
              添加组件
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Spin>
  );
};

export default AddWidgetForm;
