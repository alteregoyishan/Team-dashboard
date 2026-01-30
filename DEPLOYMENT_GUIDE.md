# Team Dashboard - Permanent Deployment Guide

## Current Status
- **Local Link**: http://localhost:8501 (only active when running)
- **Data Storage**: team_dashboard.db (SQLite database)
- **User Management**: PM_users.txt file
- **Data Capacity**: Virtually unlimited (SQLite handles TB+ data)

## Permanent Deployment Options

### 1. Streamlit Community Cloud (Recommended - FREE)

Steps:
1. Push code to GitHub repository
2. Go to https://share.streamlit.io/
3. Connect your GitHub account
4. Deploy your app
5. Get permanent URL: `https://your-app-name.streamlit.app`

**Pros**: 
- Free forever
- Automatic updates when you push to GitHub
- HTTPS security
- No server maintenance

**Cons**:
- Public (unless you upgrade)
- Limited resources

### 2. Internal Server (24/7)

Run on your company server:
```bash
# Install as service (Windows)
nohup streamlit run team_dashboard.py --server.address 0.0.0.0 --server.port 8501 &

# Access via: http://your-server-ip:8501
```

### 3. Cloud Server (AWS/Azure/GCP)

Deploy on cloud with permanent domain.

## Data Storage Details

### Local Database (本地开发): team_dashboard.db
- **Type**: SQLite (file-based database)
- **Location**: Same folder as application
- **Size**: Starts ~50KB, grows ~1KB per submission
- **Capacity**: Can handle millions of records (TB+ data)
- **Backup**: Simply copy the .db file

### 永久数据库解决方案 (生产环境)

#### 方案1: Supabase (推荐 - 免费500MB)
```bash
# 1. 注册 https://supabase.com (免费账户)
# 2. 创建项目，获取 DATABASE_URL
# 3. 添加环境变量到 Streamlit Cloud
```

#### 方案2: PlanetScale (免费5GB)
```bash
# 1. 注册 https://planetscale.com
# 2. 创建数据库，获取连接字符串
# 3. 支持 MySQL 语法
```

#### 方案3: Railway.app (免费500MB)
```bash
# 1. 注册 https://railway.app
# 2. 添加 PostgreSQL 插件
# 3. 自动生成连接URL
```

#### 方案4: Neon (免费500MB)
```bash
# 1. 注册 https://neon.tech
# 2. PostgreSQL 云数据库
# 3. 支持分支功能
```

### User Management: PM_users.txt
- **Type**: Simple text file  
- **Location**: Same folder as application
- **Function**: One username per line
- **Editable**: Through web interface or direct file edit

### Data Growth Estimation
- **1 year (250 working days, 10 users)**: ~2,500 records = ~2.5MB
- **5 years**: ~12.5MB
- **Very safe for long-term use**

### 高强度使用场景：100人每日提交

**存储计算：**
- **每条记录大小**: 约1.5KB（包含所有字段+JSON+索引开销）
- **每日数据量**: 100人 × 1.5KB = 150KB/天
- **年度数据量**: 150KB × 250工作日 = 37.5MB/年
- **免费额度可用时长**: 500MB ÷ 37.5MB = **约13年**

**分阶段存储策略：**

| 时期 | 累计数据量 | 建议方案 |
|------|------------|----------|
| **第1-3年** | < 150MB | Supabase免费版 |
| **第4-10年** | 150-400MB | 继续免费版，定期数据清理 |
| **第11+年** | > 400MB | 升级付费版($25/月) 或数据归档 |

**优化建议：**
1. **数据清理**: 超过2年的记录可导出后删除
2. **批量操作**: 避免频繁小量提交
3. **监控使用**: Supabase dashboard实时查看存储用量
4. **自动归档**: 设置定期导出历史数据

**实际监控：**
- Supabase会显示确切的存储用量
- 接近限额时会收到邮件提醒
- 可随时升级到付费版（无数据丢失）

**结论**: 100人每日使用，免费版可稳定运行10+年

## Export Capabilities

### Built-in Export Features:
1. **Excel Export**: Multi-sheet workbook with summary
2. **CSV Export**: Standard format for Excel/analysis
3. **JSON Export**: Structured data for programming

### Automatic Backups (Optional)
Add to your deployment:
```python
# Daily automatic export
import schedule
def daily_backup():
    df = get_all_submissions()
    df.to_excel(f"backup_{datetime.now().strftime('%Y%m%d')}.xlsx")
```

## 永久数据库实施步骤

### 最简方案：Supabase + Streamlit Cloud

#### 第一步：设置 Supabase 数据库（详细图解）

**1.1 注册Supabase账户**
1. 打开浏览器，访问 https://supabase.com
2. 点击右上角 "Start your project" 或 "Sign Up"
3. 选择注册方式：
   - **推荐**：点击 "Continue with GitHub"（如果有GitHub账户）
   - 或者：点击 "Continue with Google"
   - 或者：使用邮箱注册（输入邮箱和密码）
4. 完成注册后，会跳转到 Supabase Dashboard

**1.2 创建数据库项目**
1. 在 Dashboard 点击 "New project"
2. 选择组织（Organization）：
   - 如果是第一次使用，会自动创建个人组织
   - 直接选择你的用户名组织
3. 填写项目信息：
   - **Name**: `team-dashboard`（项目名称）
   - **Database Password**: 自动生成（记住这个密码！）
   - **Region**: 选择 "Southeast Asia (Singapore)" 或就近地区
   - **Pricing Plan**: 确保选择 "Free"（免费方案）
4. 点击 "Create new project"
5. 等待项目创建（约2-3分钟，会显示进度条）

**1.3 获取数据库连接字符串**
1. 项目创建完成后，点击左侧菜单 "Settings"（齿轮图标）
2. 在 Settings 页面左侧子菜单中，点击 "Database" 
3. 向下滚动找到 "Connection info" 或 "Connection parameters" 部分
4. 在连接信息区域：
   - 找到 "Connection string" 
   - 选择 "URI" 格式（不是 psql 命令格式）
   - 复制完整的连接字符串
   - 格式类似：`postgresql://postgres.[项目ID]:[YOUR-PASSWORD]@db.[项目ID].supabase.co:5432/postgres`
5. **替换密码**：将 `[YOUR-PASSWORD]` 替换为你的实际数据库密码
6. **重要**：将完整连接字符串保存到安全的地方！

**🚨 关键安全提醒：**
- **绝对不要**把包含密码的连接字符串上传到GitHub！
- **绝对不要**在代码文件中硬编码数据库密码！  
- **只在 Streamlit Cloud 环境变量中设置**
- GitHub仓库应该保持公开安全，不包含任何密码信息

**✅ 正确示例：**
你的连接字符串应该是：
`postgresql://postgres:你的实际密码@db.kxlplqmfksoqtoyzarmm.supabase.co:5432/postgres`

**🔍 如果在Database页面找不到Connection info：**
- 确保你在 **Settings** 页面，不是左侧的 "Database" 管理页面
- 在项目首页，可能有 "Connect" 或 "Project Settings" 按钮
- 或者直接在项目概览页面查看连接参数

**1.4 数据持久性说明**
✅ **是的，你电脑关机后数据完全不受影响！**
- 数据存储在 Supabase 云服务器上，不在你的电脑
- 团队成员提交数据 → 直接保存到云数据库
- 你的电脑只是开发工具，不是数据存储地点
- 即使你电脑坏了，数据依然安全存在云端

#### 第二步：准备代码推送到GitHub（完整安全流程）

**2.1 创建GitHub仓库**
1. 访问 https://github.com
2. 登录后点击右上角 "+" → "New repository"
3. 填写仓库信息：
   - **Repository name**: `team-dashboard`
   - **Description**: `Team Performance Dashboard`
   - **设为 Public**（Streamlit Cloud 免费版需要公开仓库）
   - ✅ 勾选 "Add a README file"
   - ✅ 勾选 "Add .gitignore" → 选择 "Python"
4. 点击 "Create repository"

**2.2 安全检查 - 确保代码不包含敏感信息**
在上传前，确认以下文件**不包含**任何密码或敏感信息：
- ✅ `team_dashboard.py` - 只有代码逻辑，无密码
- ✅ `database_adapter.py` - 通过环境变量读取连接
- ✅ `requirements.txt` - 只有依赖包
- ✅ `PM_users.txt` - 只有用户名，无密码
- ✅ `DEPLOYMENT_GUIDE.md` - 指导文档

**2.3 上传代码到GitHub（三种方式任选）**

**方式A：网页上传（推荐新手）**
1. 在新创建的仓库页面，点击 "uploading an existing file"
2. 将上述文件拖拽上传
3. 在底部输入提交信息："Initial dashboard upload"
4. 点击 "Commit changes"

**方式B：Git命令行**
```bash
# 在本地项目文件夹
git init
git add team_dashboard.py database_adapter.py requirements.txt PM_users.txt
git commit -m "Initial dashboard upload"
git branch -M main
git remote add origin https://github.com/你的用户名/team-dashboard.git
git push -u origin main
```

**方式C：GitHub Desktop**
1. 下载 GitHub Desktop 应用
2. Clone 仓库到本地
3. 复制文件到仓库文件夹
4. Commit 并 Push

**2.4 验证上传成功**
- 刷新GitHub仓库页面
- 确认所有文件都已上传
- **重要**：检查文件内容确保无密码泄露

#### 第三步：部署到 Streamlit Cloud 并连接云数据库

**3.1 连接Streamlit Cloud**
1. 访问 psycopg2.OperationalError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/team-dashboard/team_dashboard.py", line 1442, in <module>
    get_database_connection()
    ~~~~~~~~~~~~~~~~~~~~~~~^^
File "/mount/src/team-dashboard/team_dashboard.py", line 68, in get_database_connection
    return db_adapter.get_connection()
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^
File "/mount/src/team-dashboard/database_adapter.py", line 28, in get_connection
    conn = psycopg2.connect(self.db_url)
File "/home/adminuser/venv/lib/python3.13/site-packages/psycopg2/__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
2. 点击 "Sign up" 
3. **必须用GitHub账户登录**：点击 "Continue with GitHub"
4. 授权 Streamlit 访问你的GitHub仓库（会列出你的所有公开仓库）

**3.2 创建新应用**
1. 在 Streamlit Cloud Dashboard，点击 "New app"
2. 选择部署源：
   - **Repository**: 选择 `你的用户名/team-dashboard`
   - **Branch**: `main`（默认）
   - **Main file path**: `team_dashboard.py`
3. **关键步骤**：点击 "Advanced settings..."

**3.3 配置云数据库连接（关键步骤）**
1. 在 Advanced Settings 页面展开
2. 找到 "Environment variables" 部分
3. 添加环境变量（这里输入你的数据库连接）：
   - **Key**: `DATABASE_URL`
   - **Value**: `postgresql://postgres:你的新密码@db.kxlplqmfksoqtoyzarmm.supabase.co:5432/postgres`
   - 注意：替换"你的新密码"为重置后的实际密码
4. 点击 "Deploy!"

**3.4 部署过程监控**
1. 部署过程约3-8分钟，会显示实时日志
2. 如果出现错误，查看日志排除问题
3. 成功后会显示你的永久链接
4. 格式：`https://team-dashboard-随机字符.streamlit.app`

**3.5 首次运行验证**
1. 点击永久链接打开应用
2. 应用会自动连接到Supabase云数据库
3. 尝试提交一条测试数据
4. 检查数据是否成功保存

**连接原理说明：**
- 代码从环境变量读取 `DATABASE_URL`
- 本地开发时使用SQLite（无环境变量）
- 云端部署时使用PostgreSQL（有环境变量）
- 数据永久保存在Supabase，不在Streamlit服务器

#### 第四步：验证数据持久化
- 提交测试数据
- 重启应用（在 Streamlit Cloud 管理面板）
- 确认数据仍然存在

**验证步骤：**
1. 打开你的永久链接
2. 提交一条测试数据
3. 在 Streamlit Cloud 点击 "Reboot app"
4. 重新打开链接，确认数据还在
5. ✅ 成功！你的数据现在永久保存在云端

#### 第五步：团队使用与维护

**5.1 分享给团队**
- 将永久链接分享给所有团队成员
- 大家可以在任何地方、任何时间访问
- 无需安装任何软件

**5.2 后续代码修改**
- 修改本地代码文件
- 推送到GitHub仓库（commit & push）
- Streamlit Cloud 自动更新（约1-2分钟）
- **链接保持不变**

**5.3 数据备份建议**
- 定期使用 "Data Management" → "Export Data" 导出备份
- 建议每周导出一次Excel文件
- Supabase本身也有自动备份机制

#### 完成！你现在拥有：
✅ **永久访问链接**：团队随时可用  
✅ **云端数据库**：500MB免费空间  
✅ **自动部署**：代码改动自动更新  
✅ **数据持久化**：电脑关机不影响  
✅ **全球访问**：任何地方都能用

### 各方案对比

| 服务商 | 免费额度 | 特点 | 适合场景 | 备注 |
|--------|----------|------|----------|------|
| Supabase | 500MB + 50MB 编辑 | PostgreSQL，实时订阅 | 推荐首选 | 即插即用 |
| PlanetScale | 5GB | MySQL，分支功能 | 大数据量 | 需额外MySQL适配 |
| Railway | 500MB | 简单配置 | 快速部署 | PostgreSQL兼容 |
| Neon | 500MB | PostgreSQL，无服务器 | 技术团队 | PostgreSQL兼容 |

**为什么不推荐PlanetScale作为首选：**
- 需要额外开发MySQL适配器（当前只支持PostgreSQL）
- 连接配置更复杂（SSL证书）
- SQL语法差异需要额外处理
- 但如果你需要大容量且愿意适配，5GB确实很吸引人

### 成本预估
- **免费阶段**: 500MB = 约50万条记录 = 100人团队用10年
- **付费阶段**: 约$5-20/月，TB级容量

### 所需文件修改
1. **requirements.txt** 应包含（Python 3.13兼容版本）：
```
streamlit>=1.29.0
pandas>=2.2.0
plotly>=5.17.0
psycopg2-binary>=2.9.7
openpyxl>=3.1.2
scikit-learn>=1.4.0
numpy>=1.26.0
```

2. **team_dashboard.py** 修改数据库连接函数（见上方代码）

3. **环境变量设置**：
```
DATABASE_URL=postgresql://postgres:[password]@[host]:5432/postgres
```

## Quick Setup for Permanent Use

1. **Deploy to Streamlit Cloud** (Easiest):
   - Create GitHub repository
   - Upload your files
   - Deploy on share.streamlit.io
   - Share permanent link with team

2. **Configure Users**:
   - Edit PM_users.txt with your actual team names
   - Or use the web interface (Configuration tab)

3. **Start Using**:
   - Team accesses permanent URL
   - Data automatically saved to database
   - Export data regularly for backup

## Security Notes

- **Data Privacy**: SQLite database is local to server
- **Access Control**: Consider adding authentication for production
- **Backups**: Export data weekly/monthly
- **Updates**: Easy to update code and redeploy

## Recommended Workflow

1. **Week 1**: Deploy to Streamlit Cloud for testing
2. **Week 2**: Configure with real team members and batches  
3. **Week 3**: Team training and initial data collection
4. **Ongoing**: Regular data exports and monitoring

Your data is safe, exportable, and the solution scales well for years of use!