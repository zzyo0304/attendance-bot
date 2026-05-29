# 部署指南 — Render + 微信测试号

## 总览

```
你电脑上的代码 → GitHub → Render 自动部署 → 拿到公网域名
                                              ↓
                                微信测试号配置 URL + Token
                                              ↓
                                  扫码关注 → 开始打卡！
```

---

## 第一步：安装 Git（如果没装）

1. 下载：https://git-scm.com/download/win
2. 安装时一路默认下一步就行
3. 安装完成后，打开 PowerShell 验证：
```powershell
git --version
```

---

## 第二步：把代码推到 GitHub

### 2.1 在 GitHub 创建仓库
1. 打开 https://github.com/new
2. Repository name 填：`attendance-bot`（或你喜欢的名字）
3. **不要勾选** "Add a README file"（我们已经有代码了）
4. 点击 "Create repository"

### 2.2 推送代码
在项目目录打开 PowerShell，依次执行：
```powershell
# 进入项目目录
cd c:/Users/hh/CodeBuddy/20260529220232

# 初始化 Git
git init

# 添加所有文件
git add -A

# 提交
git commit -m "feat: 考勤打卡系统"

# 关联你的 GitHub 仓库（把 YOUR_USERNAME 换成你的 GitHub 用户名）
git remote add origin https://github.com/YOUR_USERNAME/attendance-bot.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

---

## 第三步：Render 部署

### 3.1 注册 Render
1. 打开 https://render.com
2. 点击 "Get Started" → 用 GitHub 账号登录
3. 授权 Render 访问你的 GitHub

### 3.2 创建 Web Service
1. 在 Render 面板点击 **"New +"** → **"Web Service"**
2. 选择你的 `attendance-bot` 仓库 → **"Connect"**
3. 填写以下配置：

| 配置项 | 值 |
|--------|-----|
| Name | `attendance-bot` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn -w 2 -b 0.0.0.0:10000 app:app` |
| Free Plan | ✅ 选 Free |

4. 滚动到 **Environment Variables**，添加：

| Key | Value |
|-----|-------|
| `WECHAT_TOKEN` | `your_token_here`（先随便填，等会儿改）|
| `WECHAT_APP_ID` | `your_appid_here`（先随便填）|
| `WECHAT_APP_SECRET` | `your_appsecret_here`（先随便填）|
| `SECRET_KEY` | `随机写一串英文字母数字` |
| `ADMIN_PASSWORD` | `你想设的管理后台密码` |

5. 点击 **"Create Web Service"**
6. 等待部署完成（约3-5分钟），会显示 **"Your service is live 🎉"**

### 3.3 记下域名
部署成功后，你会看到一个域名，类似：
```
https://attendance-bot.onrender.com
```
**记下来！** 这个就是你的服务器地址。

---

## 第四步：配置微信测试号

### 4.1 申请测试号
1. 打开 https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
2. 用微信扫码登录
3. 你会看到 **appID** 和 **appsecret**

### 4.2 配置接口
在测试号页面往下翻，找到 **"接口配置信息"**：

| 字段 | 值 |
|------|-----|
| URL | `https://attendance-bot.onrender.com/wechat`（换成你实际的域名）|
| Token | 自己随便起一个英文名，比如 `mytoken2024` |

先别点提交！还要去 Render 设置环境变量。

### 4.3 更新 Render 环境变量
1. 回到 Render 控制台，点击你的 `attendance-bot` 服务
2. 左侧菜单 → **"Environment"**
3. 修改以下变量为测试号上的真实值：

| Key | 值（从测试号页面复制） |
|-----|------------------------|
| `WECHAT_TOKEN` | 你刚才设的 Token，如 `mytoken2024` |
| `WECHAT_APP_ID` | 测试号页面的 `appID` |
| `WECHAT_APP_SECRET` | 测试号页面的 `appsecret` |

4. 修改后 Render 会自动重新部署（约2分钟）

### 4.4 提交验证
1. 等 Render 重新部署完成后
2. 回到微信测试号页面
3. 点击 **"接口配置信息"** 的 **"提交"** 按钮
4. 提示 "配置成功" ✅

---

## 第五步：测试

### 5.1 关注测试号
在测试号页面有一个二维码，用微信扫码关注。

### 5.2 发消息测试
在微信里给测试号发送：
- `帮助` → 看功能列表
- `设置用户名 张三` → 设置你的名字
- `上班` → 打卡上班
- `下班` → 打卡下班（自动计算工时和加班费）
- `查询` → 看今天的考勤
- `汇总` → 本月考勤汇总
- `底薪` → 查看底薪

### 5.3 管理后台
浏览器打开：`https://attendance-bot.onrender.com/admin`
- 用你设置的 `ADMIN_PASSWORD` 登录
- 可以设置底薪、补卡、导出Excel、管理节假日

---

## 常见问题

**Q: Render 免费版会休眠吗？**
A: 是的，15分钟没访问会休眠，下次访问需要30秒左右唤醒。可以接受。

**Q: 数据会丢失吗？**
A: Render 免费版使用 SQLite，磁盘有1GB持久化存储，正常不会丢数据。

**Q: 域名能自定义吗？**
A: 免费版只能用 `xxx.onrender.com`，但够用了。

**Q: 能多人用吗？**
A: 可以！每个人关注测试号后会生成不同的 OpenID，系统自动区分。

---

## 需要帮助？

部署过程中遇到任何问题，把报错信息发给我！
