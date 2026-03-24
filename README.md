# 🤖 Fakabot - 专业的 Telegram 自动发卡机器人

[![GitHub release](https://img.shields.io/github/v/release/yanguo0905/fakabot?style=flat-square)](https://github.com/yanguo0905/fakabot/releases)
[![GitHub stars](https://img.shields.io/github/stars/yanguo0905/fakabot?style=flat-square)](https://github.com/yanguo0905/fakabot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yanguo0905/fakabot?style=flat-square)](https://github.com/yanguo0905/fakabot/network)
[![GitHub issues](https://img.shields.io/github/issues/yanguo0905/fakabot?style=flat-square)](https://github.com/yanguo0905/fakabot/issues)
[![License](https://img.shields.io/badge/license-Commercial-blue.svg?style=flat-square)]()
[![Python](https://img.shields.io/badge/python-3.11-blue.svg?style=flat-square)]()
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg?style=flat-square)](https://t.me/sonhshu)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square)]()

<div align="center">

### 🚀 全自动发卡系统 | 支持多种支付方式 | 订单自动处理 | Redis 高性能缓存

💳 支付宝 · 微信 · USDT | 🐳 Docker 一键部署 | ⚡ 性能提升 100 倍

**适用场景**：知识付费 · 虚拟商品 · 在线课程 · 软件交付 · 会员服务

🎬 [在线演示](https://t.me/) · 📱 [联系客服](https://t.me/) · 📖 [完整文档](#-快速开始)

中文文档 | [English](README.en.md)

</div>

---

## ⚠️ 重要说明

当前版本已移除内置授权校验逻辑，部署时**不再需要 `license.key`**。

- ✅ 无需授权文件即可启动
- ✅ 原有支付、订单、发货等业务流程保持不变
- ✅ 历史文档中涉及授权码的步骤属于旧版本说明

---

## ✨ 核心功能

### 💳 支付系统

支持 **4 种主流支付方式**，满足不同用户需求：

| 支付方式 | 特点 | 到账速度 |
|---------|------|---------|
| **支付宝** | 当面付、扫码支付 | 实时 |
| **微信支付** | Native 支付、扫码 | 实时 |
| **USDT (TOKEN188)** | TRC20/ERC20、链上验证 | 1-3 分钟 |
| **USDT ** | 多链支持、低手续费 | 秒级 |

**特性**：
- ✅ 自动到账确认 · ✅ 支付回调处理 · ✅ 订单状态同步 · ✅ 支付超时处理

### 🎯 自动发货系统

支付成功后**自动发货**，无需人工干预：

**支持的发货方式**：

<table>
<tr>
<td>📱 <b>Telegram 群组邀请链接</b><br>（机器人自动生成一次性邀请链接，无需人工操作）</td>
<td>🔑 <b>卡密/激活码</b><br>（从库存自动提取）</td>
</tr>
<tr>
<td>📥 <b>下载链接</b><br>（自动发送）</td>
<td>📝 <b>自定义文本内容</b><br>（灵活配置）</td>
</tr>
</table>

**智能功能**：

<table>
<tr>
<td width="50%">

- ✅ **自动生成一次性邀请链接**<br>（Telegram 群组，用后即失效）
- ✅ **库存自动扣减**<br>（卡密自动提取）
- ✅ **库存不足提醒**<br>（低于阈值自动通知）

</td>
<td width="50%">

- ✅ **防重复发货**<br>（订单去重机制）
- ✅ **发货失败重试**<br>（自动重试3次）
- ✅ **发货记录追踪**<br>（完整日志）

</td>
</tr>
</table>

### ⚡ 性能优化

采用 **Redis 缓存**，性能提升 10-100 倍：

**优化项**：
- 🚀 商品列表缓存（减少 90% 数据库查询） · 🚀 用户数据缓存（响应速度提升 10 倍）
- 🚀 订单状态缓存（实时更新） · 🚀 支付状态缓存（秒级响应）

**其他优化**：
- ⚡ 频率限制（防止滥用） · ⚡ 自动降级（高负载保护） · ⚡ 连接池（提升并发） · ⚡ 异步处理（非阻塞）

### 📊 订单管理

完整的订单管理系统：

**功能列表**：

<table>
<tr>
<td width="50%">

- 📋 订单列表（今日/历史/全部）
- 🔍 订单搜索（订单号/用户/商品）
- 📝 订单详情（完整信息）

</td>
<td width="50%">

- 🔄 订单状态（待支付/已支付/已完成/已取消）
- 💰 订单统计（金额/数量）

</td>
</tr>
</table>

### 👥 用户管理

强大的用户管理功能：

**用户信息**：
- 👤 用户列表 · 📊 用户统计 · 💰 消费记录

### 🛍️ 商品管理

灵活的商品管理系统：

**商品设置**：
- ➕ 添加商品 · ✏️ 编辑商品 · 🗑️ 删除商品 · 📦 批量操作

**库存管理**：
- 📥 批量导入卡密 · 📊 库存统计 · ⚠️ 库存预警 · 🔄 自动补货提醒

### 🎨 管理后台

专业的管理后台界面：

**数据统计**：
- 📊 今日数据（订单/收入/用户）
- 📈 本月数据统计
- 💰 总收入统计

**快速操作**：
- ⚡ 一键发货 · 📢 批量通知 · 🔄 数据刷新

**系统设置**：
- ⚙️ 基础配置 · 💳 支付配置 · 📧 通知配置

---

## 🚀 快速开始

### 🎉 首次使用教程

> 💡 **适用于**：第一次部署机器人（免授权版本）

#### 第 1 步：克隆项目

```bash
git clone https://github.com/yanguo0905/fakabot.git
cd fakabot
```

#### 第 2 步：配置文件

```bash
# 复制配置示例
cp config.json.example config.json

# 编辑配置
vim config.json
```

**必须填写的内容**：

```json
{
  "BOT_TOKEN": "你的Bot Token",  // 从 @BotFather 获取
  "ADMIN_ID": 123456789,         // 你的 Telegram ID（从 @userinfobot 获取）
  "DOMAIN": "https://你的域名.com",  // 可选，没有域名可以留空
  "PAYMENTS": {
    // 支付配置（后续配置）
  }
}
```

**获取 Bot Token**：
1. 找 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`
3. 按提示创建机器人
4. 获取 Token

**获取管理员 ID**：
1. 找 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息
3. 获取你的 ID

#### 第 3 步：启动服务

```bash
# 使用 Docker Compose 启动（兼容新旧命令）
docker compose up -d || docker-compose up -d
```

#### 第 4 步：验证运行

```bash
# 查看日志
docker compose logs -f bot || docker-compose logs -f bot

# 看到机器人启动且无报错即可
```

#### 第 5 步：测试机器人

在 Telegram 搜索你的机器人，发送 `/start`

**如果看到欢迎消息，说明部署成功！** 🎉

---

### 🧭 宝塔面板命令行一步一步安装（免授权版）

> 适合你当前场景：已经在宝塔面板里打开「命令行」。

#### 0）进入部署目录

```bash
cd /www/wwwroot
```

#### 1）确认 Docker / Compose 可用

```bash
docker -v
docker compose version || docker-compose -v
```

#### 2）克隆项目（使用你的仓库）

```bash
git clone https://github.com/yanguo0905/fakabot.git
cd fakabot
```

#### 3）创建配置并填写参数

```bash
cp config.json.example config.json
vim config.json
```

最少填写：
- `BOT_TOKEN`（从 @BotFather 获取）
- `ADMIN_ID`（从 @userinfobot 获取）
- 你实际使用的支付参数

#### 4）启动服务（无需授权文件）

```bash
docker compose up -d || docker-compose up -d
```

#### 5）查看运行日志

```bash
docker compose logs -f bot || docker-compose logs -f bot
```

看到机器人启动且无报错后，`Ctrl + C` 退出日志。

#### 6）Telegram 验证

给机器人发送 `/start`，能收到欢迎消息即部署成功。

#### 7）常用维护命令

```bash
# 重启
docker compose restart || docker-compose restart

# 查看容器状态
docker compose ps || docker-compose ps

# 更新代码并重建
git pull
docker compose up -d --build || docker-compose up -d --build
```

---

### 方式一：Docker 一键部署（推荐）⭐

**最简单的部署方式，5 分钟搞定！**

```bash
# 1. 克隆项目
git clone https://github.com/yanguo0905/fakabot.git
cd fakabot

# 2. 复制配置文件
cp config.json.example config.json

# 3. 编辑配置（填写 Bot Token、管理员 ID 等）
vim config.json

# 4. 一键启动
docker compose up -d || docker-compose up -d

# 5. 查看日志
docker compose logs -f bot || docker-compose logs -f bot
```

**就这么简单！** ✅

**Docker Compose 配置**：

项目已包含 `docker-compose.yml`，自动配置：
- ✅ Fakabot 主程序 · ✅ Redis 缓存服务 · ✅ 数据持久化 · ✅ 自动重启 · ✅ 网络隔离

**常用 Docker 命令**：

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps

# 更新代码
git pull && docker-compose up -d --build

# 备份数据
tar -czf backup.tar.gz data/ config.json
```

---

### 方式二：传统部署

#### 环境要求

- **操作系统**: Linux (Ubuntu 20.04+) / macOS
- **Python**: 3.11+
- **内存**: 最低 1GB，推荐 2GB+
- **硬盘**: 最低 10GB
- **网络**: 需要访问 Telegram API

#### 部署步骤

**第 1 步：准备服务器**

推荐服务商：
- 阿里云轻量应用服务器（¥24/月）
- 腾讯云轻量应用服务器（¥25/月）
- Vultr（$5/月）
- DigitalOcean（$6/月）

配置建议：1核2GB，20GB 硬盘

**第 2 步：克隆项目**

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 克隆项目
git clone https://github.com/yanguo0905/fakabot.git
cd fakabot
```

**第 3 步：安装依赖**

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Python 3.11
apt install python3.11 python3.11-pip -y

# 安装项目依赖
pip3 install -r requirements.txt

# 安装 Redis（可选，用于缓存）
apt install redis-server -y
systemctl start redis
systemctl enable redis
```

**第 4 步：配置机器人**

1. **创建 Telegram Bot**
   - 找 [@BotFather](https://t.me/BotFather)
   - 发送 `/newbot`
   - 获取 Bot Token

2. **获取管理员 ID**
   - 找 [@userinfobot](https://t.me/userinfobot)
   - 获取你的 Telegram ID

3. **配置支付接口**
   - 支付宝/微信：申请商户号
   - USDT：注册 TOKEN188 或柠檬支付

4. **编辑配置文件**

```bash
cp config.json.example config.json
vim config.json
```

配置示例：

```json
{
  "BOT_TOKEN": "你的Bot Token",
  "ADMIN_ID": 你的Telegram ID,
  "DOMAIN": "https://你的域名.com",
  
  "PAYMENTS": {
    "alipay": {
      "enabled": true,
      "app_id": "你的支付宝AppID",
      "private_key": "你的私钥",
      "public_key": "支付宝公钥"
    },
    "wxpay": {
      "enabled": true,
      "mch_id": "你的商户号",
      "api_key": "你的API密钥"
    },
    "usdt_token188": {
      "enabled": true,
      "api_key": "你的API Key",
      "merchant_id": "你的商户号"
    }
  },
  
  "REDIS": {
    "enabled": true,
    "host": "localhost",
    "port": 6379
  }
}
```

**第 5 步：启动机器人**

方式 A：直接运行（测试用）

```bash
python3 bot.py
```

方式 B：后台运行（推荐）

```bash
nohup python3 bot.py > bot.log 2>&1 &
tail -f bot.log
```

方式 C：使用 systemd（最推荐）

```bash
# 创建服务文件
vim /etc/systemd/system/fakabot.service
```

服务文件内容：

```ini
[Unit]
Description=Fakabot Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/fakabot
ExecStart=/usr/bin/python3 /root/fakabot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
systemctl daemon-reload
systemctl start fakabot
systemctl enable fakabot
systemctl status fakabot
```

**第 6 步：验证运行**

在 Telegram 搜索你的机器人，发送 `/start`

启动成功提示（示例）：
```
✅ Bot 启动成功
✅ 数据库初始化完成
✅ 支付模块加载完成
```

---

## 📖 使用教程

### 管理员操作

#### 1. 添加商品

```
发送给机器人：
/admin → 商品管理 → 添加商品

填写信息：
- 商品名称：VIP会员
- 商品价格：99
- 商品描述：VIP会员，享受专属权益
- 发货内容：
  方式1：@your_group（群组用户名，机器人自动生成一次性邀请链接）
  方式2：https://t.me/+xxx（固定邀请链接）
  方式3：卡密内容（从库存提取）
```

**群组邀请链接说明**：
- 🔐 **自动生成**：机器人自动调用 Telegram API 生成邀请链接
- ⏱️ **一次性使用**：每个订单生成独立链接，用后即失效
- 🚫 **防止滥用**：链接只能使用1次，无法分享给他人
- ✅ **无需人工**：全程自动化，无需管理员干预

#### 2. 管理库存

```
/admin → 商品管理 → 库存管理

批量导入卡密：
发送文本文件，每行一个卡密
```

#### 3. 查看订单

```
/admin → 订单管理

可以查看：
- 今日订单
- 历史订单
- 待处理订单
- 订单详情
```

#### 4. 数据统计

```
/admin → 数据统计

查看：
- 今日收入
- 本月收入
- 订单数量
- 用户数量
```

### 用户购买流程

#### 1. 用户发送 `/start`

机器人显示：
```
👋 欢迎使用自动发卡机器人！

📦 商品列表：
1. VIP会员 - 99 USDT
2. 高级课程 - 199 USDT

点击商品查看详情
```

#### 2. 选择商品

用户点击商品 → 显示详情 → 点击购买

#### 3. 选择支付方式

```
💳 请选择支付方式：
- 支付宝
- 微信支付
- USDT
```

#### 4. 完成支付

- 扫码支付
- 支付成功后自动发货
- 收到商品内容

#### 5. 查询订单

```
发送：/orders

查看历史订单和购买记录
```

---

## 🔧 高级配置

### 配置域名和 SSL（可选但推荐）

> 💡 **说明**：域名不是必须的，但强烈推荐配置。有域名可以：
> - 配置 Webhook（比轮询更高效）
> - 配置 SSL 证书（更安全）
> - 支付回调更稳定

#### 第 1 步：购买域名

**推荐域名服务商**：

| 服务商 | 价格 | 链接 |
|---------|------|------|
| 阿里云 | ¥50-100/年 | https://wanwang.aliyun.com |
| 腾讯云 | ¥50-100/年 | https://dnspod.cloud.tencent.com |
| Namecheap | $10-15/年 | https://www.namecheap.com |
| GoDaddy | $10-15/年 | https://www.godaddy.com |

**购买流程**：
1. 访问域名服务商网站
2. 搜索你想要的域名（例如：`mybot.com`）
3. 加入购物车并支付
4. 完成实名认证（国内域名必须）

#### 第 2 步：配置 DNS 解析

**以阿里云为例**：

1. 登录阿里云控制台
2. 进入“域名”管理
3. 点击你的域名，选择“解析”
4. 添加解析记录：

**解析配置**：

| 记录类型 | 主机记录 | 记录值 | TTL |
|----------|----------|----------|-----|
| A | @ | 你的服务器IP | 600 |
| A | www | 你的服务器IP | 600 |

**示例**：
- 记录类型：`A`
- 主机记录：`@` （代表根域名，如 `mybot.com`）
- 记录值：`123.45.67.89` （你的服务器 IP）
- TTL：`600` （10分钟）

**验证解析**：
```bash
# 等待 5-10 分钟后执行
ping mybot.com

# 应该显示你的服务器 IP
```

#### 第 3 步：安装 SSL 证书（免费）

**使用 Let's Encrypt 免费证书**：

```bash
# 1. 安装 Certbot
apt update
apt install certbot -y

# 2. 停止占用 80 端口的服务（如果有）
systemctl stop nginx  # 或 systemctl stop apache2

# 3. 申请证书
certbot certonly --standalone -d mybot.com -d www.mybot.com

# 4. 按提示输入邮箱地址
# 同意服务条款：Y

# 5. 证书申请成功！
```

**证书文件位置**：
```
证书文件：/etc/letsencrypt/live/mybot.com/fullchain.pem
私钥文件：/etc/letsencrypt/live/mybot.com/privkey.pem
```

**设置自动续期**：
```bash
# 测试续期
certbot renew --dry-run

# 添加定时任务（每天凌晨2点检查）
crontab -e

# 添加以下内容：
0 2 * * * certbot renew --quiet
```

#### 第 4 步：配置 config.json

**修改配置文件**：
```bash
vim config.json
```

**更新 DOMAIN 字段**：
```json
{
  "BOT_TOKEN": "...",
  "ADMIN_ID": 123456789,
  "DOMAIN": "https://mybot.com",  // 改成你的域名，注意使用 https://
  ...
}
```

#### 第 5 步：配置 Webhook（可选）

**Webhook 比轮询更高效**：

在 `config.json` 中添加：
```json
{
  "BOT_TOKEN": "...",
  "DOMAIN": "https://mybot.com",
  "USE_WEBHOOK": true,
  "WEBHOOK_PATH": "/webhook/telegram",
  "WEBHOOK_PORT": 58002
}
```

**重启服务**：
```bash
docker-compose restart
```

### 配置 Nginx 反向代理（推荐）

> 💡 **作用**：使用 Nginx 作为反向代理，可以：
> - 配置 SSL 证书
> - 负载均衡
> - 防火墙功能
> - 更好的性能

#### 安装 Nginx

```bash
# Ubuntu/Debian
apt update
apt install nginx -y

# 启动 Nginx
systemctl start nginx
systemctl enable nginx
```

#### 创建配置文件

```bash
# 创建配置文件
vim /etc/nginx/sites-available/fakabot
```

#### HTTP 配置（基础版）

```nginx
server {
    listen 80;
    server_name mybot.com www.mybot.com;
    
    location / {
        proxy_pass http://127.0.0.1:58001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### HTTPS 配置（完整版，推荐）

```nginx
# HTTP 自动跳转 HTTPS
server {
    listen 80;
    server_name mybot.com www.mybot.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS 配置
server {
    listen 443 ssl http2;
    server_name mybot.com www.mybot.com;
    
    # SSL 证书配置
    ssl_certificate /etc/letsencrypt/live/mybot.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mybot.com/privkey.pem;
    
    # SSL 优化配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 反向代理配置
    location / {
        proxy_pass http://127.0.0.1:58001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Webhook 配置（如果使用）
    location /webhook/telegram {
        proxy_pass http://127.0.0.1:58002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 启用配置

```bash
# 创建软链接
ln -s /etc/nginx/sites-available/fakabot /etc/nginx/sites-enabled/

# 测试配置
nginx -t

# 重启 Nginx
systemctl restart nginx
```

#### 验证配置

```bash
# 访问你的域名
curl https://mybot.com

# 应该返回机器人的响应
```
```

### 配置 Redis 缓存

```bash
# 安装 Redis
apt install redis-server -y

# 配置 Redis
vim /etc/redis/redis.conf

# 设置密码（可选）
requirepass 你的密码

# 设置最大内存
maxmemory 256mb
maxmemory-policy allkeys-lru

# 重启 Redis
systemctl restart redis
```

### 数据备份

```bash
# 备份数据库
cp fakabot.db fakabot.db.backup

# 定时备份（每天凌晨3点）
crontab -e

# 添加：
0 3 * * * cp /root/fakabot/fakabot.db /root/backup/fakabot_$(date +\%Y\%m\%d).db
```

---

## 🧾 部署与维护说明

- 当前版本为 **免授权运行**：不需要 `license.key`，也没有续费步骤。
- 若你看到旧文档里“授权码/续费/到期”相关内容，以本文档最新内容为准。
- 推荐优先使用 Docker Compose（`docker compose`）部署，维护成本最低。

---

## ❓ 常见问题

### 部署相关

**Q: 还需要授权码吗？**  
A: 不需要。当前版本部署与运行均不依赖 `license.key`。

**Q: 旧文档里出现授权码步骤怎么办？**  
A: 直接跳过即可；请以本 README 的“重要说明”和“快速开始”为准。

**Q: 包含技术支持吗？**  
A: 是，建议优先通过仓库 Issue 或你使用的交付渠道反馈问题。

### 技术相关

**Q: 需要什么配置的服务器？**  
A: 最低 1核1GB，推荐 1核2GB。月费约 $5-10。

**Q: 必须要域名吗？**  
A: 不是必须的，但强烈推荐。域名可以配置 SSL，更安全。

**Q: 支持哪些支付方式？**  
A: 机器人支持支付宝、微信、USDT (TOKEN188)、USDT (柠檬支付)。

**Q: 可以自定义界面吗？**  
A: 可以，修改配置文件中的文案和按钮即可。

**Q: 支持多语言吗？**  
A: 目前支持中文，可以自行翻译配置文件实现多语言。

**Q: 数据存储在哪里？**  
A: 使用 SQLite 数据库，存储在 fakabot.db 文件中。

**Q: 如何备份数据？**  
A: 定期备份 fakabot.db 文件和 config.json 配置文件。

### 使用相关

**Q: 如何添加商品？**  
A: 发送 /admin → 商品管理 → 添加商品。

**Q: 如何查看收入？**  
A: 发送 /admin → 数据统计。

**Q: 支持自动发货吗？**  
A: 是的，支付成功后自动发货，无需人工干预。

**Q: 支持分销吗？**  
A: 当前版本不支持，后续版本会添加。

---

## 🔐 运行与安全说明

当前项目已移除内置授权校验逻辑，默认按“免授权”方式运行。

**建议你重点关注以下安全项：**
- ✅ 正确配置支付回调地址与签名密钥
- ✅ 为服务器开启防火墙与最小权限
- ✅ 定期备份 `fakabot.db` 与 `config.json`
- ✅ 使用 HTTPS / 反向代理保护管理入口

---

## 📞 联系我们

- **Telegram 客服**: [@sonhshu](https://t.me/sonhshu)

---

## ⚠️ 免责声明

**本项目仅供学习和合法商业用途使用。**

### 使用本项目即表示您同意：

- ✅ 遵守所在国家/地区的法律法规
- ✅ 仅用于合法的商业用途
- ✅ 对使用本项目产生的任何后果自行负责
- ✅ 不侵犯他人合法权益

### 开发者声明：

- 📢 本项目开发者不对用户的使用行为负责
- 📢 不对因使用本项目造成的任何损失负责
- 📢 保留随时停止服务的权利
- 📢 保留拒绝向任何用户提供服务的权利

### 明确禁止用途：

- ❌ 赌博、色情等非法内容销售
- ❌ 侵犯知识产权的内容分发
- ❌ 诈骗、传销等违法行为
- ❌ 洗钱、非法资金转移
- ❌ 其他违反法律法规的行为

### 合法用途示例：

- ✅ 在线课程、教育内容销售
- ✅ 正版软件与数字内容销售
- ✅ 会员服务
- ✅ 数字艺术品、音乐销售
- ✅ 电子书、文档资料销售

**如发现用户将本项目用于非法用途，开发者将立即终止服务并配合相关部门调查。**

---

## 📄 许可证

请遵守仓库中许可证文件与服务条款中的约定；本文档不再包含任何授权码激活要求。

详见 [服务条款](TERMS_OF_SERVICE.md)

---

<div align="center">

**专业的 Telegram 自动发卡解决方案**

Made with ❤️ by Fakabot Team

[开始使用](#-快速开始) · [查看演示](https://t.me/) · [联系客服](https://t.me/)

</div>
