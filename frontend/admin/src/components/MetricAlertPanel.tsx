/**
 * 指标告警配置面板
 * 支持阈值告警、同比告警、环比告警
 */
import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Switch,
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Typography,
  Empty,
  Tooltip,
  Divider,
} from 'antd';
import {
  BellOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { metricService, MetricAlert, MetricAlertCreate } from '../services/metricService';

const { Text } = Typography;

interface MetricAlertPanelProps {
  visible: boolean;
  metricId: string;
  metricName: string;
  onClose: () => void;
}

// 告警类型选项
const ALERT_TYPE_OPTIONS = [
  { value: 'threshold', label: '阈值告警', description: '当指标值超过/低于设定阈值时触发' },
  { value: 'yoy', label: '同比告警', description: '与去年同期对比，变化超过阈值时触发' },
  { value: 'mom', label: '环比告警', description: '与上期对比，变化超过阈值时触发' },
];

// 条件选项
const CONDITION_OPTIONS = [
  { value: 'gt', label: '大于 (>)' },
  { value: 'gte', label: '大于等于 (>=)' },
  { value: 'lt', label: '小于 (<)' },
  { value: 'lte', label: '小于等于 (<=)' },
  { value: 'eq', label: '等于 (=)' },
];

// 通知渠道选项
const CHANNEL_OPTIONS = [
  { value: 'email', label: '邮件' },
  { value: 'webhook', label: 'Webhook' },
  { value: 'sms', label: '短信' },
];

const MetricAlertPanel: React.FC<MetricAlertPanelProps> = ({
  visible,
  metricId,
  metricName,
  onClose,
}) => {
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState<MetricAlert[]>([]);
  const [formVisible, setFormVisible] = useState(false);
  const [editingAlert, setEditingAlert] = useState<MetricAlert | null>(null);
  const [form] = Form.useForm();
  const [alertType, setAlertType] = useState<string>('threshold');

  useEffect(() => {
    if (visible && metricId) {
      fetchAlerts();
    }
  }, [visible, metricId]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await metricService.listAlerts(metricId);
      setAlerts(data);
    } catch (error) {
      message.error('获取告警列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingAlert(null);
    form.resetFields();
    form.setFieldsValue({
      alert_type: 'threshold',
      condition: 'gt',
      enabled: true,
      notify_channels: [],
    });
    setAlertType('threshold');
    setFormVisible(true);
  };

  const handleEdit = (record: MetricAlert) => {
    setEditingAlert(record);
    form.setFieldsValue({
      ...record,
    });
    setAlertType(record.alert_type);
    setFormVisible(true);
  };

  const handleDelete = async (alertId: string) => {
    try {
      await metricService.deleteAlert(alertId);
      message.success('删除成功');
      fetchAlerts();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleToggle = async (alertId: string, enabled: boolean) => {
    try {
      await metricService.toggleAlert(alertId, enabled);
      message.success(enabled ? '已启用' : '已禁用');
      fetchAlerts();
    } catch (error) {
      message.error('操作失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      const alertData: MetricAlertCreate = {
        ...values,
        metric_id: metricId,
      };

      if (editingAlert) {
        await metricService.updateAlert(editingAlert.id, alertData);
        message.success('更新成功');
      } else {
        await metricService.createAlert(alertData);
        message.success('创建成功');
      }

      setFormVisible(false);
      fetchAlerts();
    } catch (error) {
      console.error('提交失败:', error);
    }
  };

  const getAlertTypeTag = (type: string) => {
    const config: Record<string, { color: string; text: string }> = {
      threshold: { color: 'blue', text: '阈值' },
      yoy: { color: 'purple', text: '同比' },
      mom: { color: 'orange', text: '环比' },
    };
    const { color, text } = config[type] || { color: 'default', text: type };
    return <Tag color={color}>{text}</Tag>;
  };

  const getConditionText = (condition: string) => {
    const map: Record<string, string> = {
      gt: '>',
      gte: '>=',
      lt: '<',
      lte: '<=',
      eq: '=',
    };
    return map[condition] || condition;
  };

  const columns = [
    {
      title: '告警名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: MetricAlert) => (
        <Space>
          <Text strong>{text}</Text>
          {!record.enabled && <Tag color="default">已禁用</Tag>}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'alert_type',
      key: 'alert_type',
      width: 80,
      render: (type: string) => getAlertTypeTag(type),
    },
    {
      title: '条件',
      key: 'condition',
      width: 150,
      render: (_: any, record: MetricAlert) => {
        if (record.alert_type === 'threshold') {
          return (
            <Text code>
              值 {getConditionText(record.condition)} {record.threshold_value}
            </Text>
          );
        } else {
          return (
            <Text code>
              变化 {getConditionText(record.condition)} {record.change_percent}%
            </Text>
          );
        }
      },
    },
    {
      title: '触发次数',
      dataIndex: 'trigger_count',
      key: 'trigger_count',
      width: 90,
      render: (count: number) => (
        <Tag color={count > 0 ? 'red' : 'green'}>
          {count}
        </Tag>
      ),
    },
    {
      title: '状态',
      key: 'enabled',
      width: 80,
      render: (_: any, record: MetricAlert) => (
        <Switch
          size="small"
          checked={record.enabled}
          onChange={(checked) => handleToggle(record.id, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, record: MetricAlert) => (
        <Space>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此告警?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Modal
        title={
          <Space>
            <BellOutlined />
            <span>告警管理 - {metricName}</span>
          </Space>
        }
        open={visible}
        onCancel={onClose}
        width={700}
        footer={null}
      >
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            新建告警
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={alerts}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="small"
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无告警规则"
              />
            ),
          }}
        />
      </Modal>

      {/* 创建/编辑告警表单 */}
      <Modal
        title={editingAlert ? '编辑告警' : '新建告警'}
        open={formVisible}
        onOk={handleSubmit}
        onCancel={() => setFormVisible(false)}
        width={500}
        okText={editingAlert ? '保存' : '创建'}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="告警名称"
            rules={[{ required: true, message: '请输入告警名称' }]}
          >
            <Input placeholder="如：销售额超过100万告警" />
          </Form.Item>

          <Form.Item
            name="alert_type"
            label="告警类型"
            rules={[{ required: true }]}
          >
            <Select
              options={ALERT_TYPE_OPTIONS}
              onChange={(value) => setAlertType(value)}
            />
          </Form.Item>

          <Form.Item
            name="condition"
            label="触发条件"
            rules={[{ required: true }]}
          >
            <Select options={CONDITION_OPTIONS} />
          </Form.Item>

          {alertType === 'threshold' ? (
            <Form.Item
              name="threshold_value"
              label="阈值"
              rules={[{ required: true, message: '请输入阈值' }]}
            >
              <InputNumber
                style={{ width: '100%' }}
                placeholder="如：1000000"
              />
            </Form.Item>
          ) : (
            <Form.Item
              name="change_percent"
              label="变化百分比阈值 (%)"
              rules={[{ required: true, message: '请输入变化百分比' }]}
            >
              <InputNumber
                style={{ width: '100%' }}
                placeholder="如：10 表示变化超过10%时触发"
                min={0}
                max={100}
              />
            </Form.Item>
          )}

          <Divider />

          <Form.Item
            name="notify_channels"
            label="通知渠道"
          >
            <Select
              mode="multiple"
              placeholder="选择通知方式"
              options={CHANNEL_OPTIONS}
            />
          </Form.Item>

          <Form.Item
            name="enabled"
            label="启用状态"
            valuePropName="checked"
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default MetricAlertPanel;
