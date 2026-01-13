/**
 * InsightConditionPanel 组件
 * 用于编辑洞察分析的查询条件（时间范围、维度筛选、聚合粒度）
 */
import React, { useState, useEffect } from 'react';
import { Modal, Form, DatePicker, Select, Input, Space, Button, Typography, Divider, Alert } from 'antd';
import { PlusOutlined, MinusCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type { InsightConditions } from '../types/dashboard';
import dayjs, { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;
const { Option } = Select;
const { Text } = Typography;

interface InsightConditionPanelProps {
  visible: boolean;
  currentConditions?: InsightConditions;
  onSubmit: (conditions: InsightConditions) => void;
  onCancel: () => void;
}

export const InsightConditionPanel: React.FC<InsightConditionPanelProps> = ({
  visible,
  currentConditions,
  onSubmit,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [useRelativeRange, setUseRelativeRange] = useState(true);

  useEffect(() => {
    if (visible && currentConditions) {
      // 初始化表单值
      const timeRange = currentConditions.time_range;
      if (timeRange?.relative_range) {
        setUseRelativeRange(true);
        form.setFieldsValue({
          relative_range: timeRange.relative_range,
          aggregation_level: currentConditions.aggregation_level,
        });
      } else if (timeRange?.start && timeRange?.end) {
        setUseRelativeRange(false);
        form.setFieldsValue({
          date_range: [dayjs(timeRange.start), dayjs(timeRange.end)],
          aggregation_level: currentConditions.aggregation_level,
        });
      } else {
        form.setFieldsValue({
          aggregation_level: currentConditions.aggregation_level,
        });
      }

      // 设置维度筛选
      if (currentConditions.dimension_filters) {
        const filters = Object.entries(currentConditions.dimension_filters).map(
          ([key, value]) => ({
            dimension: key,
            value: String(value),
          })
        );
        form.setFieldsValue({ dimension_filters: filters });
      }
    } else if (visible) {
      // 新建时使用默认值
      form.resetFields();
      setUseRelativeRange(true);
      form.setFieldsValue({
        relative_range: 'last_30_days',
        aggregation_level: 'day',
      });
    }
  }, [visible, currentConditions, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      const conditions: InsightConditions = {
        aggregation_level: values.aggregation_level,
      };

      // 处理时间范围
      if (useRelativeRange && values.relative_range) {
        conditions.time_range = {
          relative_range: values.relative_range,
        };
      } else if (!useRelativeRange && values.date_range) {
        conditions.time_range = {
          start: values.date_range[0].format('YYYY-MM-DD'),
          end: values.date_range[1].format('YYYY-MM-DD'),
        };
      }

      // 处理维度筛选
      if (values.dimension_filters && values.dimension_filters.length > 0) {
        conditions.dimension_filters = {};
        values.dimension_filters.forEach((filter: any) => {
          if (filter?.dimension && filter?.value) {
            conditions.dimension_filters![filter.dimension] = filter.value;
          }
        });
      }

      onSubmit(conditions);
    } catch (error) {
      console.error('表单验证失败:', error);
    }
  };

  return (
    <Modal
      title="调整洞察分析条件"
      open={visible}
      onOk={handleSubmit}
      onCancel={onCancel}
      width={600}
      okText="应用"
      cancelText="取消"
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          relative_range: 'last_30_days',
          aggregation_level: 'day',
        }}
      >
        <Divider orientation="left">时间范围</Divider>
        
        <Form.Item label="时间范围类型">
          <Space>
            <Button
              type={useRelativeRange ? 'primary' : 'default'}
              onClick={() => setUseRelativeRange(true)}
            >
              相对时间
            </Button>
            <Button
              type={!useRelativeRange ? 'primary' : 'default'}
              onClick={() => setUseRelativeRange(false)}
            >
              绝对时间
            </Button>
          </Space>
        </Form.Item>

        {useRelativeRange ? (
          <Form.Item
            name="relative_range"
            label="相对时间范围"
            rules={[{ required: true, message: '请选择时间范围' }]}
          >
            <Select placeholder="请选择时间范围">
              <Option value="last_7_days">最近7天</Option>
              <Option value="last_30_days">最近30天</Option>
              <Option value="last_90_days">最近90天</Option>
              <Option value="last_6_months">最近6个月</Option>
              <Option value="last_year">最近1年</Option>
              <Option value="this_month">本月</Option>
              <Option value="last_month">上月</Option>
              <Option value="this_quarter">本季度</Option>
              <Option value="last_quarter">上季度</Option>
              <Option value="this_year">今年</Option>
              <Option value="last_year_full">去年</Option>
            </Select>
          </Form.Item>
        ) : (
          <Form.Item
            name="date_range"
            label="日期范围"
            rules={[{ required: true, message: '请选择日期范围' }]}
          >
            <RangePicker style={{ width: '100%' }} />
          </Form.Item>
        )}

        <Divider orientation="left">聚合粒度</Divider>

        <Form.Item
          name="aggregation_level"
          label="数据聚合粒度"
          rules={[{ required: true, message: '请选择聚合粒度' }]}
        >
          <Select placeholder="请选择聚合粒度">
            <Option value="hour">小时</Option>
            <Option value="day">天</Option>
            <Option value="week">周</Option>
            <Option value="month">月</Option>
            <Option value="quarter">季度</Option>
            <Option value="year">年</Option>
          </Select>
        </Form.Item>

        <Divider orientation="left">维度筛选（可选）</Divider>
        
        <Alert 
          message="什么是维度筛选？" 
          description="维度筛选用于细化数据范围。例如：只分析“华东地区”的销售数据，或只看“产品A”的趋势。"
          type="info" 
          showIcon 
          style={{ marginBottom: 16, fontSize: 12 }}
        />

        <Form.List name="dimension_filters">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field, index) => (
                <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item
                    {...field}
                    name={[field.name, 'dimension']}
                    rules={[{ required: true, message: '请输入维度名称' }]}
                    style={{ marginBottom: 0, flex: 1 }}
                  >
                    <Input placeholder="例如：region（地区）、category（类别）" />
                  </Form.Item>
                  <Form.Item
                    {...field}
                    name={[field.name, 'value']}
                    rules={[{ required: true, message: '请输入筛选值' }]}
                    style={{ marginBottom: 0, flex: 1 }}
                  >
                    <Input placeholder="例如：华东、产品A" />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                </Space>
              ))}
              <Form.Item>
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  添加维度筛选
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>

        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
          <InfoCircleOutlined style={{ marginRight: 4 }} />
          不确定如何填写？可以留空，直接点击“应用”按钮生成洞察。
        </Text>
      </Form>
    </Modal>
  );
};

export default InsightConditionPanel;
