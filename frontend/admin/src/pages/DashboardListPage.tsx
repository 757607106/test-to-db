import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Modal,
  Form,
  Input,
  Space,
  message,
  Popconfirm,
  Typography,
  Tag,
  Empty,
  Spin,
  Select,
  Pagination,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ShareAltOutlined,
  DashboardOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { dashboardService } from '../services/dashboardService';
import type { DashboardListItem, DashboardCreate, DashboardUpdate } from '../types/dashboard';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const DashboardListPage: React.FC = () => {
  const navigate = useNavigate();
  const [dashboards, setDashboards] = useState<DashboardListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(12);
  const [scope, setScope] = useState<'mine' | 'shared' | 'public' | 'all'>('mine');
  const [searchText, setSearchText] = useState<string>('');
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [editingDashboard, setEditingDashboard] = useState<DashboardListItem | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchDashboards();
  }, [page, pageSize, scope]);

  const fetchDashboards = async () => {
    setLoading(true);
    try {
      const response = await dashboardService.getDashboards({
        scope,
        page,
        page_size: pageSize,
        search: searchText || undefined,
      });
      setDashboards(response.items);
      setTotal(response.total);
    } catch (error) {
      message.error('获取Dashboard列表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchDashboards();
  };

  const showModal = (dashboard?: DashboardListItem) => {
    setEditingDashboard(dashboard || null);
    form.resetFields();
    if (dashboard) {
      form.setFieldsValue({
        name: dashboard.name,
        description: dashboard.description,
        is_public: dashboard.is_public,
        tags: dashboard.tags || [],
      });
    }
    setModalVisible(true);
  };

  const handleCancel = () => {
    setModalVisible(false);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      if (editingDashboard) {
        const updateData: DashboardUpdate = {
          name: values.name,
          description: values.description || undefined,
          is_public: values.is_public,
          tags: values.tags || undefined,
        };
        await dashboardService.updateDashboard(editingDashboard.id, updateData);
        message.success('Dashboard更新成功');
      } else {
        const createData: DashboardCreate = {
          name: values.name,
          description: values.description || undefined,
          is_public: values.is_public || false,
          tags: values.tags || undefined,
        };
        const newDashboard = await dashboardService.createDashboard(createData);
        message.success('Dashboard创建成功');
        // 创建后直接跳转到编辑页
        navigate(`/dashboards/${newDashboard.id}`);
        return;
      }

      setModalVisible(false);
      fetchDashboards();
    } catch (error) {
      message.error('保存Dashboard失败');
      console.error(error);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await dashboardService.deleteDashboard(id);
      message.success('Dashboard删除成功');
      fetchDashboards();
    } catch (error) {
      message.error('删除Dashboard失败');
      console.error(error);
    }
  };

  const handleView = (id: number) => {
    navigate(`/dashboards/${id}`);
  };

  const handlePageChange = (newPage: number, newPageSize?: number) => {
    setPage(newPage);
    if (newPageSize && newPageSize !== pageSize) {
      setPageSize(newPageSize);
    }
  };

  const getPermissionTag = (level?: string) => {
    switch (level) {
      case 'owner':
        return <Tag color="gold">拥有者</Tag>;
      case 'editor':
        return <Tag color="blue">编辑者</Tag>;
      case 'viewer':
        return <Tag color="green">查看者</Tag>;
      default:
        return null;
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Title level={4}>
              <DashboardOutlined style={{ marginRight: 8 }} />
              我的Dashboard
            </Title>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => showModal()}>
              创建Dashboard
            </Button>
          </div>

          <Space size="middle" style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space>
              <Select
                value={scope}
                onChange={(value) => {
                  setScope(value);
                  setPage(1);
                }}
                style={{ width: 120 }}
              >
                <Option value="mine">我的</Option>
                <Option value="shared">共享给我</Option>
                <Option value="public">公开的</Option>
                <Option value="all">全部</Option>
              </Select>

              <Input.Search
                placeholder="搜索Dashboard名称"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                onSearch={handleSearch}
                style={{ width: 300 }}
                allowClear
              />
            </Space>
          </Space>
        </div>

        <Spin spinning={loading}>
          {dashboards.length === 0 ? (
            <Empty
              description="暂无Dashboard"
              style={{ margin: '60px 0' }}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button type="primary" icon={<PlusOutlined />} onClick={() => showModal()}>
                创建第一个Dashboard
              </Button>
            </Empty>
          ) : (
            <>
              <Row gutter={[16, 16]}>
                {dashboards.map((dashboard) => (
                  <Col xs={24} sm={12} md={8} lg={6} key={dashboard.id}>
                    <Card
                      hoverable
                      style={{ height: '100%' }}
                      onClick={() => handleView(dashboard.id)}
                      actions={[
                        <EyeOutlined key="view" onClick={(e) => { e.stopPropagation(); handleView(dashboard.id); }} />,
                        dashboard.permission_level === 'owner' || dashboard.permission_level === 'editor' ? (
                          <EditOutlined
                            key="edit"
                            onClick={(e) => {
                              e.stopPropagation();
                              showModal(dashboard);
                            }}
                          />
                        ) : null,
                        dashboard.permission_level === 'owner' ? (
                          <Popconfirm
                            title="确定要删除这个Dashboard吗？"
                            onConfirm={(e) => {
                              e?.stopPropagation();
                              handleDelete(dashboard.id);
                            }}
                            okText="是"
                            cancelText="否"
                            onCancel={(e) => e?.stopPropagation()}
                          >
                            <DeleteOutlined
                              key="delete"
                              onClick={(e) => e.stopPropagation()}
                            />
                          </Popconfirm>
                        ) : null,
                      ].filter(Boolean)}
                    >
                      <div style={{ minHeight: 150 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                          <Title level={5} ellipsis={{ rows: 1 }} style={{ margin: 0, flex: 1 }}>
                            {dashboard.name}
                          </Title>
                          {dashboard.is_public && <Tag color="cyan" style={{ marginLeft: 8 }}>公开</Tag>}
                        </div>

                        <Paragraph
                          ellipsis={{ rows: 2 }}
                          type="secondary"
                          style={{ minHeight: 44, marginBottom: 12 }}
                        >
                          {dashboard.description || '暂无描述'}
                        </Paragraph>

                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {dashboard.widget_count} 个组件
                            </Text>
                            {getPermissionTag(dashboard.permission_level)}
                          </div>

                          {dashboard.tags && dashboard.tags.length > 0 && (
                            <div>
                              {dashboard.tags.slice(0, 2).map((tag, index) => (
                                <Tag key={index} style={{ marginRight: 4, marginBottom: 4 }}>
                                  {tag}
                                </Tag>
                              ))}
                              {dashboard.tags.length > 2 && (
                                <Tag style={{ marginBottom: 4 }}>+{dashboard.tags.length - 2}</Tag>
                              )}
                            </div>
                          )}

                          <Text type="secondary" style={{ fontSize: 12 }}>
                            创建于 {new Date(dashboard.created_at).toLocaleDateString()}
                          </Text>
                        </Space>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>

              <div style={{ marginTop: 24, textAlign: 'right' }}>
                <Pagination
                  current={page}
                  pageSize={pageSize}
                  total={total}
                  onChange={handlePageChange}
                  showSizeChanger
                  showTotal={(total) => `共 ${total} 个Dashboard`}
                  pageSizeOptions={['12', '24', '48', '96']}
                />
              </div>
            </>
          )}
        </Spin>
      </Card>

      <Modal
        title={editingDashboard ? '编辑Dashboard' : '创建Dashboard'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={handleCancel}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ is_public: false, tags: [] }}>
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入Dashboard名称' },
              { max: 255, message: '名称不能超过255个字符' },
            ]}
          >
            <Input placeholder="例如：销售数据看板" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <TextArea
              rows={4}
              placeholder="请输入Dashboard的描述信息"
              maxLength={1000}
              showCount
            />
          </Form.Item>

          <Form.Item name="is_public" label="公开设置" valuePropName="checked">
            <Select>
              <Option value={false}>私有</Option>
              <Option value={true}>公开</Option>
            </Select>
          </Form.Item>

          <Form.Item name="tags" label="标签">
            <Select
              mode="tags"
              placeholder="输入标签后按回车添加"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DashboardListPage;
