# RoboParts 完整部署操作手册

> 目标域名：**roboparts.cn** | 部署平台：Vercel | 后端：Supabase
> 预计总耗时：30分钟（大部分是等待时间）

---

## 第一步：注册域名（5分钟）

### 操作
1. 登录腾讯云控制台：https://console.cloud.tencent.com
2. 搜索「域名注册」或直接访问：https://buy.cloud.tencent.com/domain
3. 搜索 `roboparts.cn`
4. 选择购买年限（建议选3年，约150元）
5. 填写域名持有者信息（实名认证，需要身份证信息）
6. 完成支付

### 实名认证
- .cn 域名**必须实名认证**才能解析使用
- 提交后通常 **1个工作日** 审核通过
- 审核通过前可以先用 Vercel 临时域名预览

### 注册完成后
记录你的域名：`roboparts.cn`

---

## 第二步：创建 Supabase 项目（10分钟）

### 2.1 注册并创建项目
1. 打开 https://supabase.com ，点击 **Start your project**
2. 用 GitHub 账号登录（刚才已经登录了）
3. 点击 **New Project**，填写：
   - **Name**: `roboparts`
   - **Database Password**: 设一个密码，记下来！
   - **Region**: 选择 `Northeast Asia (Tokyo)` 或 `Southeast Asia (Singapore)`
   - **Plan**: Free
4. 点击 **Create new project**，等待2-3分钟创建完成

### 2.2 执行数据库脚本
1. 项目创建完成后，左侧菜单点击 **SQL Editor**
2. 点击 **New query**
3. 打开项目文件 `supabase/schema.sql`，复制**全部内容**
4. 粘贴到 SQL Editor 中
5. 点击右下角 **Run** 按钮
6. 看到 "Success" 提示即可

### 2.3 获取 API 密钥
1. 左侧菜单点击 **Settings**（齿轮图标）
2. 点击 **API**
3. 复制以下两个值：
   - **Project URL**: 形如 `https://xxxxx.supabase.co`
   - **anon public** Key: 形如 `eyJhbGciOiJI...`

### 2.4 修改配置文件
打开项目中的 `js/config.js`，替换为你的实际值：

```js
const SUPABASE_CONFIG = {
  url: 'https://你的项目ID.supabase.co',     // ← 替换这里
  anonKey: '你的anon public key',              // ← 替换这里
};
```

### 2.5 创建存储桶
1. 左侧菜单点击 **Storage**
2. 点击 **New Bucket**
3. Bucket name 填：`stl-uploads`
4. Public bucket 选择 **ON**（公开访问）
5. 点击 **Create bucket**

---

## 第三步：部署到 Vercel（10分钟）

### 3.1 创建 Vercel 账号
1. 打开 https://vercel.com
2. 点击 **Sign Up**，选择 **Continue with GitHub**
3. 授权 Vercel 访问你的 GitHub
4. 选择免费 Hobby 计划

### 3.2 导入 GitHub 仓库
1. Vercel Dashboard 点击 **Add New** → **Project**
2. 在 Import Git Repository 中找到 `lm203688/roboparts`
3. 点击 **Import**
4. 框架预设选择 **Other**（不需要构建）
5. 直接点击 **Deploy**
6. 等待1-2分钟，部署完成

### 3.3 记录 Vercel 临时域名
部署成功后，Vercel 会给你一个临时域名，形如：
`roboparts-lm203688.vercel.app`

此时访问这个临时域名，网站应该已经可以正常显示了！

---

## 第四步：绑定自定义域名（5分钟）

### 4.1 在 Vercel 添加域名
1. Vercel Dashboard → 你的项目 → **Settings** → **Domains**
2. 输入：`roboparts.cn`
3. 点击 **Add**
4. 再添加：`www.roboparts.cn`
5. 点击 **Add**

Vercel 会显示需要配置的 DNS 记录。

### 4.2 在腾讯云配置 DNS 解析
1. 登录腾讯云控制台：https://console.cloud.tencent.com/cns
2. 找到 `roboparts.cn` 域名，点击 **解析**
3. 添加以下记录：

| 主机记录 | 记录类型 | 记录值 | TTL |
|----------|----------|--------|-----|
| `@` | A | `76.76.21.21` | 600 |
| `www` | CNAME | `cname.vercel-dns.com` | 600 |

> 注意：`76.76.21.21` 是 Vercel 的 IP，`cname.vercel-dns.com` 是 Vercel 的 CNAME。
> 如果 Vercel 显示的值不同，以 Vercel Dashboard 显示的为准。

### 4.3 等待 DNS 生效
- DNS 解析通常 **5分钟-48小时** 生效
- 大部分情况 **10分钟内** 即可
- Vercel 会在域名生效后自动配置 HTTPS 证书

---

## 第五步：验证部署

域名生效后，逐项检查：

- [ ] `https://roboparts.cn/` — 网站正常显示
- [ ] `https://www.roboparts.cn/` — 能正常访问（重定向到主域名）
- [ ] `https://roboparts.cn/sitemap.xml` — 返回 XML 内容
- [ ] `https://roboparts.cn/robots.txt` — 返回 robots 内容
- [ ] 点击「登录/注册」— 弹出登录框（测试 Supabase 连接）
- [ ] 社区板块 — 发帖/评论功能正常
- [ ] STL 下载 — 点击下载按钮能下载 .stl 文件
- [ ] 3D 预览 — 点击预览按钮能看到 3D 模型

---

## 第六步：SEO 提交（5分钟）

### 6.1 百度搜索资源平台
1. 打开 https://ziyuan.baidu.com
2. 用百度账号登录
3. 点击「用户中心」→「添加站点」
4. 输入 `https://roboparts.cn`
5. 验证方式选择 **HTML标签验证**
6. 将验证 meta 标签添加到 `index.html` 的 `<head>` 中
7. 在「数据引入」→「链接提交」中提交 `https://roboparts.cn/sitemap.xml`

### 6.2 Google Search Console
1. 打开 https://search.google.com/search-console
2. 点击「添加资源」
3. 选择「网域」，输入 `roboparts.cn`
4. 验证方式选择 **DNS 记录验证**（和域名绑定一起做）
5. 在「站点地图」中提交 `https://roboparts.cn/sitemap.xml`

### 6.3 Bing Webmaster Tools
1. 打开 https://www.bing.com/webmasters
2. 用 Microsoft 账号登录
3. 导入 Google Search Console 数据（最快方式）

---

## 架构总览

```
用户浏览器
    ↓
roboparts.cn (HTTPS)
    ↓
Vercel CDN (全球加速)
    ↓
静态文件 (index.html + CSS + JS + STL)
    ↓
Supabase (Auth + PostgreSQL + Storage)
    ├── 用户注册/登录
    ├── 社区帖子/评论/点赞
    └── STL 上传存储
```

## 费用清单

| 项目 | 费用 | 周期 |
|------|------|------|
| 域名 roboparts.cn | ~35元/年（首年） | 按年 |
| Vercel 部署 | 免费 | 永久 |
| Supabase 免费层 | 免费（500MB数据库/月） | 永久 |
| CDN/HTTPS | 免费 | 永久 |
| **合计** | **~35元/年** | |

## 更新代码流程

后续修改网站后，推送代码即可自动部署：

```bash
cd robot-parts-platform
git add -A
git commit -m "更新描述"
git push
```

Vercel 会自动检测 GitHub push 并重新部署，约1分钟生效。

---

## 常见问题

### Q: 域名实名认证要多久？
A: 通常1个工作日，审核通过前 Vercel 临时域名照常可用。

### Q: Supabase 免费层够用吗？
A: 免费层支持 500MB 数据库 + 50MB 文件存储 + 50000月活用户，初期完全够用。

### Q: DNS 一直不生效怎么办？
A: 确认腾讯云 DNS 记录格式正确（不要带多余空格），用 `nslookup roboparts.cn` 检查。

### Q: 网站打开慢怎么办？
A: Vercel 自带全球CDN，国内访问也很快。如果仍慢，可以后续切换到 Cloudflare Pages（有国内节点）。
