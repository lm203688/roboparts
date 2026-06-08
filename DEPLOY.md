# RoboLink 部署指南

## 一、域名注册（你来做）

### 推荐域名
- **robolink.cn**（首选，如果可用）
- **roboparts.cn**
- **jixierenjian.com**
- 或其他你觉得好的名字

### 注册渠道（任选）
1. **阿里云万网**: https://wanwang.aliyun.com（.cn域名首选，30-55元/年）
2. **腾讯云DNSPod**: https://dnspod.cloud.tencent.com
3. **Namesilo**: https://www.namesilo.com（海外域名）

> 注册好后，记录你的域名，后续配置需要用到。

---

## 二、Supabase 后端配置（你来做，5分钟）

### 步骤
1. 打开 https://supabase.com ，注册免费账号
2. 点击 "New Project"，创建新项目
   - Name: `robolink`
   - Database Password: 设一个密码（记住它）
   - Region: 选 Northeast Asia (Tokyo) 或 Singapore
3. 等待项目创建完成（约2分钟）
4. 进入项目 > Settings > API，复制：
   - **Project URL** → 粘贴到 `js/config.js` 的 `url`
   - **anon public** Key → 粘贴到 `js/config.js` 的 `anonKey`
5. 进入项目 > SQL Editor，粘贴 `supabase/schema.sql` 的全部内容，点击 "Run"
6. 进入项目 > Storage，点击 "New Bucket"，创建名为 `stl-uploads` 的 bucket

### config.js 示例（替换后）
```js
const SUPABASE_CONFIG = {
  url: 'https://xxxxx.supabase.co',
  anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx',
};
```

---

## 三、部署到 Vercel（推荐，免费）

### 方法A：通过 Vercel CLI
```bash
# 安装 Vercel CLI
npm i -g vercel

# 在项目目录下执行
cd robot-parts-platform
vercel

# 按提示操作，首次需要登录
# 部署成功后会得到一个 xxx.vercel.app 的临时域名
```

### 方法B：通过 GitHub（推荐）
1. 将 `robot-parts-platform` 推到 GitHub 仓库
2. 打开 https://vercel.com ，用 GitHub 登录
3. 点击 "Import Project"，选择你的仓库
4. 直接点 "Deploy"，等待完成

### 绑定自定义域名
1. Vercel Dashboard > 你的项目 > Settings > Domains
2. 添加你的域名（如 robolink.cn）
3. Vercel 会给你一条 CNAME 记录：
   ```
   类型: CNAME
   主机记录: www（或 @）
   记录值: cname.vercel-dns.com
   ```
4. 去你的域名注册商的 DNS 管理页面，添加这条记录
5. 等 DNS 生效（5分钟-48小时），Vercel 会自动配置 HTTPS

---

## 四、部署到 Cloudflare Pages（备选）

1. 打开 https://pages.cloudflare.com
2. 连接你的 GitHub 仓库，或直接上传
3. 构建设置：
   - Build command: （留空，静态站点不需要）
   - Output directory: `/`（根目录）
4. 部署完成后，在 Custom Domains 添加你的域名
5. 去域名 DNS 添加 CNAME 指向 `your-project.pages.dev`

---

## 五、SEO 验证清单

部署成功后，检查以下项目：

- [ ] 访问 `https://你的域名/`，确认网站正常显示
- [ ] 访问 `https://你的域名/sitemap.xml`，确认能返回XML
- [ ] 访问 `https://你的域名/robots.txt`，确认能返回内容
- [ ] 用 [Google Rich Results Test](https://search.google.com/test/rich-results) 测试结构化数据
- [ ] 在 Google Search Console 添加你的域名
- [ ] 在百度搜索资源平台添加你的域名
- [ ] 提交 sitemap URL 给 Google 和百度

### 百度站长平台
https://ziyuan.baidu.com
- 添加站点
- 验证所有权（HTML标签验证，最简单）
- 提交 sitemap

### Google Search Console
https://search.google.com/search-console
- 添加资源
- DNS 验证
- 提交 sitemap

---

## 六、佣金追踪系统说明

### 3D打印订单追踪
- 用户点击"委托代打"时，系统生成唯一追踪码（如 `RLAX3K7B2M`）
- 追踪码写入 Supabase `print_orders` 表
- 跳转到嘉立创时URL带上 `?ref=RLAX3K7B2M`
- 后续可对接嘉立创API自动匹配订单状态

### 零件导购追踪
- 在 `js/config.js` 中设置 `AFFILIATE_CONFIG.enabled = true`
- 配置各品牌的购买链接模板
- 用户点击"去购买"时自动记录到 `product_clicks` 表
- 后续可对接淘宝客/1688联盟API获取佣金

---

## 七、数据流图

```
用户访问 → Cloudflare CDN → Vercel Edge → 静态HTML/CSS/JS
                                            ↓
                                    Supabase Auth (登录)
                                    Supabase DB (帖子/评论)
                                    Supabase Storage (用户上传STL)
```

## 八、文件结构

```
robot-parts-platform/
├── index.html          # 主页面（含JSON-LD结构化数据）
├── sitemap.xml          # 搜索引擎站点地图
├── robots.txt           # 爬虫规则
├── vercel.json          # Vercel部署配置
├── _headers             # Cloudflare Pages缓存规则
├── config.js            # ⚠️ 需要你修改：Supabase凭据
├── css/
│   └── style.css        # 样式
├── js/
│   ├── config.js        # ⚠️ 配置文件
│   ├── data.js          # 零件数据
│   ├── auth.js          # 认证模块（Supabase + localStorage降级）
│   ├── app.js           # 应用逻辑 v2（后端集成）
│   └── stl-viewer.js    # Three.js 3D预览
├── stl/                 # 12个STL文件
├── data/                # 监控JSON数据
├── supabase/
│   └── schema.sql       # ⚠️ 需要在Supabase SQL Editor执行
├── gen_stl.py           # STL生成脚本
└── README.md
```
