import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Popconfirm,
  Checkbox,
  Tabs,
  Typography,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  KeyOutlined,
  UserOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  TenantUser,
  UserPermissions,
  PermissionTemplates,
  getTenantUsers,
  createTenantUser,
  updateTenantUser,
  updateUserPermissions,
  toggleUserStatus,
  deleteTenantUser,
  getPermissionTemplates,
  getCurrentTenant,
  TenantInfo,
} from '../services/tenantUsers';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;

const UsersPage: React.FC = () => {
  const { user } = useAuth();
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [tenant, setTenant] = useState<TenantInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  
  // Modal states
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [permissionModalVisible, setPermissionModalVisible] = useState(false);
  const [selectedUser, setSelectedUser] = useState<TenantUser | null>(null);
  const [permissionTemplates, setPermissionTemplates] = useState<PermissionTemplates | null>(null);
  
  // Forms
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [permissionForm] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await getTenantUsers();
      setUsers(response.users);
      setTotal(response.total);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchTenant = async () => {
    try {
      const data = await getCurrentTenant();
      setTenant(data);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载租户信息失败');
    }
  };

  const fetchPermissionTemplates = async () => {
    try {
      const data = await getPermissionTemplates();
      setPermissionTemplates(data);
    } catch (error: any) {
      console.error('加载权限模板失败:', error);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchTenant();
    fetchPermissionTemplates();
  }, []);

  // Create user
  const handleCreate = async (values: any) => {
    try {
      await createTenantUser({
        username: values.username,
        email: values.email,
        password: values.password,
        display_name: values.display_name,
        role: values.role || 'user',
      });
      message.success('用户创建成功');
      setCreateModalVisible(false);
      createForm.resetFields();
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '创建用户失败');
    }
  };

  // Edit user
  const handleEdit = (record: TenantUser) => {
    setSelectedUser(record);
    editForm.setFieldsValue({
      display_name: record.display_name,
      role: record.role,
    });
    setEditModalVisible(true);
  };

  const handleEditSubmit = async (values: any) => {
    if (!selectedUser) return;
    try {
      await updateTenantUser(selectedUser.id, {
        display_name: values.display_name,
        role: values.role,
      });
      message.success('用户更新成功');
      setEditModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '更新用户失败');
    }
  };

  // Permissions
  const handleEditPermissions = (record: TenantUser) => {
    setSelectedUser(record);
    const permissions = record.permissions || { menus: [], features: {} };
    permissionForm.setFieldsValue({
      menus: permissions.menus || [],
      features: permissions.features || {},
    });
    setPermissionModalVisible(true);
  };

  const handlePermissionsSubmit = async () => {
    if (!selectedUser) return;
    try {
      const values = permissionForm.getFieldsValue();
      await updateUserPermissions(selectedUser.id, {
        permissions: {
          menus: values.menus || [],
          features: values.features || {},
        },
      });
      message.success('权限更新成功');
      setPermissionModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '更新权限失败');
    }
  };

  // Toggle status
  const handleToggleStatus = async (record: TenantUser) => {
    try {
      await toggleUserStatus(record.id);
      message.success(`用户已${record.is_active ? '禁用' : '启用'}`);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '切换用户状态失败');
    }
  };

  // Delete user
  const handleDelete = async (userId: number) => {
    try {
      await deleteTenantUser(userId);
      message.success('用户删除成功');
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除用户失败');
    }
  };

  const columns: ColumnsType<TenantUser> = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (text, record) => (
        <Space>
          <UserOutlined />
          <span>{text}</span>
          {record.id === user?.id && <Tag color="blue">当前</Tag>}
        </Space>
      ),
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (text) => text || '-',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role) => {
        const colorMap: Record<string, string> = {
          super_admin: 'red',
          tenant_admin: 'orange',
          user: 'blue',
        };
        const labelMap: Record<string, string> = {
          super_admin: '超级管理员',
          tenant_admin: '租户管理员',
          user: '普通用户',
        };
        return <Tag color={colorMap[role] || 'default'}>{labelMap[role] || role}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive) => (
        <Tag color={isActive ? 'green' : 'red'}>
          {isActive ? '已启用' : '已禁用'}
        </Tag>
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      render: (date) => (date ? new Date(date).toLocaleString('zh-CN') : '从未登录'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => {
        const isCurrentUser = record.id === user?.id;
        const isAdmin = record.role === 'tenant_admin' || record.role === 'super_admin';
        
        return (
          <Space size="small">
            <Tooltip title="编辑">
              <Button
                type="text"
                icon={<EditOutlined />}
                onClick={() => handleEdit(record)}
              />
            </Tooltip>
            
            {!isAdmin && (
              <Tooltip title="权限设置">
                <Button
                  type="text"
                  icon={<KeyOutlined />}
                  onClick={() => handleEditPermissions(record)}
                />
              </Tooltip>
            )}
            
            {!isCurrentUser && (
              <>
                <Tooltip title={record.is_active ? '禁用' : '启用'}>
                  <Switch
                    size="small"
                    checked={record.is_active}
                    onChange={() => handleToggleStatus(record)}
                    disabled={isAdmin && user?.role !== 'super_admin'}
                  />
                </Tooltip>
                
                <Popconfirm
                  title="删除用户"
                  description="确定要删除此用户吗？"
                  onConfirm={() => handleDelete(record.id)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Tooltip title="删除">
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={isAdmin && user?.role !== 'super_admin'}
                    />
                  </Tooltip>
                </Popconfirm>
              </>
            )}
          </Space>
        );
      },
    },
  ];

  const menuLabels: Record<string, string> = {
    chat: '智能查询',
    connections: '数据库连接',
    training: '智能训练中心',
    llm_configs: '模型配置',
    agents: '智能体配置',
    users: '用户管理',
  };

  const featureLabels: Record<string, string> = {
    view: '查看',
    create: '创建',
    edit: '编辑',
    delete: '删除',
    query: '查询',
    publish: '发布',
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>用户管理</Title>
            {tenant && (
              <Text type="secondary">所属公司：{tenant.display_name}</Text>
            )}
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchUsers}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              添加用户
            </Button>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个用户`,
          }}
        />
      </Card>

      {/* Create User Modal */}
      <Modal
        title="添加新用户"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
          </Form.Item>
          
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          
          <Form.Item
            name="display_name"
            label="显示名称"
          >
            <Input placeholder="显示名称（选填）" />
          </Form.Item>
          
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password placeholder="请输入密码" />
          </Form.Item>
          
          <Form.Item
            name="role"
            label="角色"
            initialValue="user"
          >
            <Select>
              <Select.Option value="user">普通用户</Select.Option>
              {user?.role === 'super_admin' && (
                <Select.Option value="tenant_admin">租户管理员</Select.Option>
              )}
            </Select>
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button onClick={() => {
                setCreateModalVisible(false);
                createForm.resetFields();
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        title="编辑用户"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          setSelectedUser(null);
        }}
        footer={null}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditSubmit}
        >
          <Form.Item
            name="display_name"
            label="显示名称"
          >
            <Input placeholder="请输入显示名称" />
          </Form.Item>
          
          <Form.Item
            name="role"
            label="角色"
          >
            <Select disabled={selectedUser?.id === user?.id}>
              <Select.Option value="user">普通用户</Select.Option>
              {user?.role === 'super_admin' && (
                <Select.Option value="tenant_admin">租户管理员</Select.Option>
              )}
            </Select>
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
              <Button onClick={() => {
                setEditModalVisible(false);
                setSelectedUser(null);
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Permissions Modal */}
      <Modal
        title={`权限设置 - ${selectedUser?.username}`}
        open={permissionModalVisible}
        onCancel={() => {
          setPermissionModalVisible(false);
          setSelectedUser(null);
        }}
        onOk={handlePermissionsSubmit}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        <Form form={permissionForm} layout="vertical">
          <Tabs
            items={[
              {
                key: 'menus',
                label: '菜单权限',
                children: (
                  <Form.Item name="menus">
                    <Checkbox.Group style={{ width: '100%' }}>
                      <Space direction="vertical">
                        {permissionTemplates?.available_menus.map((menu) => (
                          <Checkbox key={menu} value={menu}>
                            {menuLabels[menu] || menu}
                          </Checkbox>
                        ))}
                      </Space>
                    </Checkbox.Group>
                  </Form.Item>
                ),
              },
              {
                key: 'features',
                label: '功能权限',
                children: (
                  <div>
                    {permissionTemplates?.available_menus.map((menu) => (
                      <div key={menu} style={{ marginBottom: '16px' }}>
                        <Text strong>{menuLabels[menu] || menu}</Text>
                        <Form.Item name={['features', menu]} noStyle>
                          <Checkbox.Group style={{ marginLeft: '16px', marginTop: '8px' }}>
                            <Space wrap>
                              {permissionTemplates.available_features[menu]?.map((feature) => (
                                <Checkbox key={feature} value={feature}>
                                  {featureLabels[feature] || feature}
                                </Checkbox>
                              ))}
                            </Space>
                          </Checkbox.Group>
                        </Form.Item>
                      </div>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        </Form>
      </Modal>
    </div>
  );
};

export default UsersPage;
