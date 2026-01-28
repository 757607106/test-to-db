import React, { useState, useEffect } from 'react';
import { 
  Card, Form, Switch, InputNumber, Select, Button, 
  Space, message, Spin, Divider, Typography, Alert, Tooltip
} from 'antd';
import { 
  SaveOutlined, ReloadOutlined, QuestionCircleOutlined,
  DatabaseOutlined, SearchOutlined, SettingOutlined
} from '@ant-design/icons';
import { 
  getSQLEnhancementConfig, 
  updateSQLEnhancementConfig, 
  resetSQLEnhancementConfig,
  SQLEnhancementConfig,
  DEFAULT_SQL_ENHANCEMENT_CONFIG
} from '../services/systemConfig';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

const SQLEnhancementConfigPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<SQLEnhancementConfig>(DEFAULT_SQL_ENHANCEMENT_CONFIG);

  // 加载配置
  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await getSQLEnhancementConfig();
      const data = response.data;
      setConfig(data);
      form.setFieldsValue(data);
    } catch (error) {
      console.error('Failed to load config:', error);
      message.error('加载配置失败');
      // 使用默认配置
      form.setFieldsValue(DEFAULT_SQL_ENHANCEMENT_CONFIG);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
  }, []);

  // 保存配置
  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await updateSQLEnhancementConfig(values);
      setConfig(values);
      message.success('配置保存成功');
    } catch (error) {
      console.error('Failed to save config:', error);
      message.error('保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  // 重置配置
  const handleReset = async () => {
    try {
      setSaving(true);
      const response = await resetSQLEnhancementConfig();
      const newConfig = response.data.config;
      setConfig(newConfig);
      form.setFieldsValue(newConfig);
      message.success('配置已重置为默认值');
    } catch (error) {
      console.error('Failed to reset config:', error);
      message.error('重置配置失败');
    } finally {
      setSaving(false);
    }
  };

  const labelWithTooltip = (label: string, tooltip: string) => (
    <Space>
      {label}
      <Tooltip title={tooltip}>
        <QuestionCircleOutlined style={{ color: '#999' }} />
      </Tooltip>
    </Space>
  );

  return (
    <div style={{ padding: '24px', maxWidth: 900 }}>
      <Card
        title={
          <Space>
            <SettingOutlined />
            <span>SQL 增强功能配置</span>
          </Space>
        }
        extra={
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={handleReset}
              loading={saving}
            >
              重置默认
            </Button>
            <Button 
              type="primary" 
              icon={<SaveOutlined />} 
              onClick={handleSave}
              loading={saving}
            >
              保存配置
            </Button>
          </Space>
        }
      >
        <Alert
          message="SQL 增强功能说明"
          description="这些配置控制 SQL 生成过程中的增强功能。启用相关功能可以提高 SQL 生成的准确性，但可能会增加响应时间。"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            initialValues={DEFAULT_SQL_ENHANCEMENT_CONFIG}
          >
            {/* QA 样本检索配置 */}
            <Card 
              type="inner" 
              title={
                <Space>
                  <SearchOutlined />
                  <span>QA 样本检索配置</span>
                </Space>
              }
              style={{ marginBottom: 16 }}
            >
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                启用后，系统会从历史成功的查询中检索相似样本，作为 SQL 生成的参考。
                这可以帮助 LLM 学习正确的 JOIN 方式和字段选择。
              </Paragraph>
              
              <Form.Item
                name="qa_sample_enabled"
                label={labelWithTooltip('启用 QA 样本检索', '开启后会从历史查询中检索相似样本作为参考')}
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                name="qa_sample_min_similarity"
                label={labelWithTooltip('最小相似度阈值', '只有相似度高于此阈值的样本才会被使用 (0-1)')}
              >
                <InputNumber 
                  min={0} 
                  max={1} 
                  step={0.05} 
                  style={{ width: 200 }}
                  formatter={(value) => `${((value as number) * 100).toFixed(0)}%`}
                  parser={(value) => (Number(value?.replace('%', '')) / 100) as 0 | 1}
                />
              </Form.Item>

              <Form.Item
                name="qa_sample_top_k"
                label={labelWithTooltip('最大样本数量', '最多使用多少个相似样本')}
              >
                <InputNumber min={1} max={10} style={{ width: 200 }} />
              </Form.Item>

              <Form.Item
                name="qa_sample_verified_only"
                label={labelWithTooltip('仅使用已验证样本', '只使用经过人工验证的高质量样本')}
                valuePropName="checked"
              >
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
            </Card>

            {/* 指标库配置 */}
            <Card 
              type="inner" 
              title={
                <Space>
                  <DatabaseOutlined />
                  <span>指标库配置</span>
                </Space>
              }
              style={{ marginBottom: 16 }}
            >
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                启用后，系统会将预定义的业务指标（如销售额、利润率等）注入到 SQL 生成提示中，
                确保 LLM 使用正确的计算公式，保证口径一致。
              </Paragraph>

              <Form.Item
                name="metrics_enabled"
                label={labelWithTooltip('启用指标库', '将预定义的业务指标公式注入到 SQL 生成提示中')}
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                name="metrics_max_count"
                label={labelWithTooltip('最大指标数量', '最多注入多少个相关指标')}
              >
                <InputNumber min={1} max={10} style={{ width: 200 }} />
              </Form.Item>
            </Card>

            {/* 枚举值提示配置 */}
            <Card 
              type="inner" 
              title="枚举值提示配置"
              style={{ marginBottom: 16 }}
            >
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                启用后，系统会将字段的可选值（如状态、类型等枚举字段）注入到提示中，
                帮助 LLM 生成正确的 WHERE 条件。
              </Paragraph>

              <Form.Item
                name="enum_hints_enabled"
                label={labelWithTooltip('启用枚举值提示', '将字段可选值注入到 SQL 生成提示中')}
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                name="enum_max_values"
                label={labelWithTooltip('每字段最大枚举值数', '每个字段最多显示多少个可选值')}
              >
                <InputNumber min={5} max={50} style={{ width: 200 }} />
              </Form.Item>
            </Card>

            {/* 流程优化配置 */}
            <Card 
              type="inner" 
              title="流程优化配置"
              style={{ marginBottom: 16 }}
            >
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                这些配置控制查询处理流程的优化，可以减少不必要的步骤，提高响应速度。
              </Paragraph>

              <Form.Item
                name="simplified_flow_enabled"
                label={labelWithTooltip('启用简化流程', '对于明确的查询跳过不必要的处理步骤')}
                valuePropName="checked"
              >
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>

              <Form.Item
                name="skip_clarification_for_clear_queries"
                label={labelWithTooltip('明确查询跳过澄清', '当查询意图明确时跳过澄清步骤')}
                valuePropName="checked"
              >
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>

              <Form.Item
                name="cache_mode"
                label={labelWithTooltip('缓存模式', 'simple: 仅精确匹配缓存; full: 包含语义相似度缓存')}
              >
                <Select style={{ width: 200 }}>
                  <Option value="simple">简单模式 (仅精确匹配)</Option>
                  <Option value="full">完整模式 (含语义缓存)</Option>
                </Select>
              </Form.Item>
            </Card>
          </Form>
        </Spin>
      </Card>
    </div>
  );
};

export default SQLEnhancementConfigPage;
