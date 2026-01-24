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
      message.error(error.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const fetchTenant = async () => {
    try {
      const data = await getCurrentTenant();
      setTenant(data);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to load tenant info');
    }
  };

  const fetchPermissionTemplates = async () => {
    try {
      const data = await getPermissionTemplates();
      setPermissionTemplates(data);
    } catch (error: any) {
      console.error('Failed to load permission templates:', error);
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
      message.success('User created successfully');
      setCreateModalVisible(false);
      createForm.resetFields();
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to create user');
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
      message.success('User updated successfully');
      setEditModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to update user');
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
      message.success('Permissions updated successfully');
      setPermissionModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to update permissions');
    }
  };

  // Toggle status
  const handleToggleStatus = async (record: TenantUser) => {
    try {
      await toggleUserStatus(record.id);
      message.success(`User ${record.is_active ? 'disabled' : 'enabled'} successfully`);
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to toggle user status');
    }
  };

  // Delete user
  const handleDelete = async (userId: number) => {
    try {
      await deleteTenantUser(userId);
      message.success('User deleted successfully');
      fetchUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const columns: ColumnsType<TenantUser> = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      render: (text, record) => (
        <Space>
          <UserOutlined />
          <span>{text}</span>
          {record.id === user?.id && <Tag color="blue">Me</Tag>}
        </Space>
      ),
    },
    {
      title: 'Display Name',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (text) => text || '-',
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role) => {
        const colorMap: Record<string, string> = {
          super_admin: 'red',
          tenant_admin: 'orange',
          user: 'blue',
        };
        const labelMap: Record<string, string> = {
          super_admin: 'Super Admin',
          tenant_admin: 'Tenant Admin',
          user: 'User',
        };
        return <Tag color={colorMap[role] || 'default'}>{labelMap[role] || role}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive) => (
        <Tag color={isActive ? 'green' : 'red'}>
          {isActive ? 'Active' : 'Inactive'}
        </Tag>
      ),
    },
    {
      title: 'Last Login',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      render: (date) => (date ? new Date(date).toLocaleString() : 'Never'),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => {
        const isCurrentUser = record.id === user?.id;
        const isAdmin = record.role === 'tenant_admin' || record.role === 'super_admin';
        
        return (
          <Space size="small">
            <Tooltip title="Edit">
              <Button
                type="text"
                icon={<EditOutlined />}
                onClick={() => handleEdit(record)}
              />
            </Tooltip>
            
            {!isAdmin && (
              <Tooltip title="Permissions">
                <Button
                  type="text"
                  icon={<KeyOutlined />}
                  onClick={() => handleEditPermissions(record)}
                />
              </Tooltip>
            )}
            
            {!isCurrentUser && (
              <>
                <Tooltip title={record.is_active ? 'Disable' : 'Enable'}>
                  <Switch
                    size="small"
                    checked={record.is_active}
                    onChange={() => handleToggleStatus(record)}
                    disabled={isAdmin && user?.role !== 'super_admin'}
                  />
                </Tooltip>
                
                <Popconfirm
                  title="Delete User"
                  description="Are you sure you want to delete this user?"
                  onConfirm={() => handleDelete(record.id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Tooltip title="Delete">
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
    chat: 'Intelligent Query',
    connections: 'DB Connections',
    training: 'Training Center',
    llm_configs: 'LLM Configuration',
    agents: 'Agent Profiles',
    users: 'User Management',
  };

  const featureLabels: Record<string, string> = {
    view: 'View',
    create: 'Create',
    edit: 'Edit',
    delete: 'Delete',
    query: 'Query',
    publish: 'Publish',
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>User Management</Title>
            {tenant && (
              <Text type="secondary">Company: {tenant.display_name}</Text>
            )}
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchUsers}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalVisible(true)}
            >
              Add User
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
            showTotal: (total) => `Total ${total} users`,
          }}
        />
      </Card>

      {/* Create User Modal */}
      <Modal
        title="Add New User"
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
            label="Username"
            rules={[
              { required: true, message: 'Please enter username' },
              { min: 3, message: 'Username must be at least 3 characters' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="Username" />
          </Form.Item>
          
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter email' },
              { type: 'email', message: 'Please enter a valid email' },
            ]}
          >
            <Input placeholder="Email" />
          </Form.Item>
          
          <Form.Item
            name="display_name"
            label="Display Name"
          >
            <Input placeholder="Display Name (optional)" />
          </Form.Item>
          
          <Form.Item
            name="password"
            label="Password"
            rules={[
              { required: true, message: 'Please enter password' },
              { min: 6, message: 'Password must be at least 6 characters' },
            ]}
          >
            <Input.Password placeholder="Password" />
          </Form.Item>
          
          <Form.Item
            name="role"
            label="Role"
            initialValue="user"
          >
            <Select>
              <Select.Option value="user">User</Select.Option>
              {user?.role === 'super_admin' && (
                <Select.Option value="tenant_admin">Tenant Admin</Select.Option>
              )}
            </Select>
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                Create
              </Button>
              <Button onClick={() => {
                setCreateModalVisible(false);
                createForm.resetFields();
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        title="Edit User"
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
            label="Display Name"
          >
            <Input placeholder="Display Name" />
          </Form.Item>
          
          <Form.Item
            name="role"
            label="Role"
          >
            <Select disabled={selectedUser?.id === user?.id}>
              <Select.Option value="user">User</Select.Option>
              {user?.role === 'super_admin' && (
                <Select.Option value="tenant_admin">Tenant Admin</Select.Option>
              )}
            </Select>
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                Save
              </Button>
              <Button onClick={() => {
                setEditModalVisible(false);
                setSelectedUser(null);
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Permissions Modal */}
      <Modal
        title={`Edit Permissions - ${selectedUser?.username}`}
        open={permissionModalVisible}
        onCancel={() => {
          setPermissionModalVisible(false);
          setSelectedUser(null);
        }}
        onOk={handlePermissionsSubmit}
        width={600}
      >
        <Form form={permissionForm} layout="vertical">
          <Tabs
            items={[
              {
                key: 'menus',
                label: 'Menu Access',
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
                label: 'Feature Permissions',
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
