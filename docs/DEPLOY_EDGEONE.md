# EdgeOne Pages 部署说明（李文亚 Wiki）

## 一、先说结论：EdgeOne 能不能用，取决于你有没有「已备案的域名」

腾讯云官方文档（Pages → 域名管理）明确写了三条规则：

| 项目加速区域 | 用平台默认域名（项目域名/部署域名）访问 | 绑定自定义域名 |
|---|---|---|
| 中国大陆可用区 / 全球（含中国大陆） | **只能用系统预览链接，有效期 3 小时**，超时返回 401 | **必须先在工信部完成 ICP 备案** |
| 全球可用区（**不含**中国大陆） | 非中国大陆网络可访问；**中国大陆网络返回 401** | 无需备案 |

也就是说：
- **有已备案域名** → EdgeOne Pages 是很合适的选择（免费、国内节点加速、自动 HTTPS、支持拖放/ Git / CLI 部署）；
- **没有备案域名** → EdgeOne Pages 的默认域名**不适合给国内用户长期访问**（要么 3 小时过期，要么国内 401）。

## 二、本实例（国内机房）实测各平台可达性

| 目标 | 结果 |
|---|---|
| https://bdydgz114514.github.io/ | 200 / 1.0s（机房网络可通） |
| https://www.netlify.com/ | 200 / 0.9s |
| https://pages.dev/ | 301 / 0.8s |
| https://edgeone.ai/ | 200 / 0.7s |
| https://gitee.com/ | 200 / 1.5s |

注意：机房网络通常比**家庭宽带**对境外站点更友好。GitHub Pages 在不少家用宽带上会打不开或很慢，因此原站仅供备用。

## 三、EdgeOne Pages 部署步骤（三种方式任选）

### 方式 1：Pages Drop 拖放（最简单，免命令行）
1. 打开 EdgeOne Pages 控制台 → Pages Drop；
2. 把本目录的 `wiki_upload/` 文件夹（或解压 `李文亚Wiki_上传包.zip` 得到的目录）**整个拖进上传区**；
3. 等待部署完成，得到预览链接。

### 方式 2：Git 导入
1. 在 EdgeOne Pages 里选择「导入 Git 仓库」，授权 GitHub；
2. 选择 `bdydgz114514/liwenya-wiki`（源码仓库）；
3. 构建命令留空（站点已构建好），输出目录填 `site/dist`；若平台要求必须构建，填 `npm install && npm run build`，输出目录 `site/dist`。

### 方式 3：CLI
```bash
npm i -g edgeone        # 安装 CLI
edgeone login           # 浏览器/令牌登录
cd <解压后的 wiki_upload 目录>
edgeone pages deploy .  # 部署当前目录（具体子命令以 CLI --help 为准）
```

## 四、免备案时的替代选择

| 方案 | 国内可用性 | 备注 |
|---|---|---|
| 单文件 HTML（`李文亚Wiki_单文件版.html`） | ✅ 完全离线 | 最省事，双击即看 |
| 离线 ZIP + `启动Wiki.bat` | ✅ 完全离线 | 1247 页 + 全文搜索 |
| Cloudflare Pages / Netlify | ⚠️ 多数地区可访问，速度中等 | 免备案，拖拽上传即可 |
| Gitee Pages | ✅ 国内快 | 需实名 + 人工审核 |
| 自己的国内服务器 / 本实例 8898 端口 | ✅ 最快 | 实例关机后失效 |

生成时间：2026-09-23