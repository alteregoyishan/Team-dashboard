# RMSI Daily Task Team Performance Dashboard

## 安全说明

### 密码管理

本系统使用两种认证方式：

1. **Employee Code（默认）**：用户使用 PM.xlsx 中的 Employee Code 登录
2. **自定义密码**：用户可以在首次登录后修改密码，存储在 `user_passwords.json`

### user_passwords.json 安全性

- **是否安全上传 GitHub？**
  - ✅ 理论上安全：密码使用 SHA256 + 随机盐值哈希，无法逆向破解
  - ⚠️ 但仍建议：添加到 `.gitignore`，避免暴露用户名列表
  
- **本地开发**：
  ```bash
  # user_passwords.json 已添加到 .gitignore
  # 每个开发者本地生成自己的密码文件
  ```

- **云端部署建议**：
  1. **使用环境变量**（推荐）：将密码存储在 Streamlit Cloud Secrets
  2. **使用数据库**：将密码哈希存入数据库表
  3. **使用云存储**：使用 Supabase Storage 或 AWS S3

### 云端部署时密码同步

**Streamlit Cloud / Heroku**：
- 文件系统是临时的，每次重启会丢失 `user_passwords.json`
- **解决方案**：
  1. 使用数据库（PostgreSQL）存储密码
  2. 或使用 Streamlit Secrets + 环境变量

**自托管服务器**：
- 文件系统持久化，`user_passwords.json` 可正常读写

## 新用户密码设置流程

1. Admin 在 Configuration → User Management 添加新用户
2. 系统检查是否有 Employee Code：
   - 有：用户使用 Employee Code 登录
   - 无：系统生成临时密码，Admin 发送给用户
3. 用户首次登录后，在侧边栏 "Change Password" 修改密码

## Admin 特殊说明

- Admin 登录后不显示 "Daily Task Entry"（Admin 不需要提交任务）
- Admin 只能访问 Data Management 和 Configuration
- Admin 密码通过环境变量 `ADMIN_ACCESS_CODE` 设置（默认：PM_ADMIN）

## 部署指南

### 本地运行

```bash
# 激活虚拟环境
.\.venv\Scripts\activate

# 运行应用
streamlit run team_dashboard.py
```

### Streamlit Cloud 部署

1. 推送代码到 GitHub（确保 `user_passwords.json` 在 `.gitignore` 中）
2. 在 Streamlit Cloud 创建应用
3. 配置 Secrets（Settings → Secrets）：
   ```toml
   ADMIN_ACCESS_CODE = "your_admin_password"
   DATABASE_URL = "your_postgres_connection_string"
   ```

### 环境变量

- `ADMIN_ACCESS_CODE`：管理员密码（默认：PM_ADMIN）
- `DATABASE_URL`：数据库连接字符串（可选，Supabase/PostgreSQL）

## PM.xlsx 文件格式

需要包含以下列：

| name | Employee Code | TEAM FUNCTION |
|------|---------------|---------------|
| John Doe | EMP001 | PM |
| Jane Smith | EMP002 | QA |

- `name` / `Name`：用户姓名
- `Employee Code` / `employee code`：员工编号（用于默认登录）
- `TEAM FUNCTION` / `Team Function`：团队职能
