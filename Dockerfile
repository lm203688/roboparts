# RoboParts MCP Server — Dockerfile for Glama server introspection
# Glama 自动扫描仓库根目录的 Dockerfile，拉起容器做 MCP 握手 + introspection 检查，
# 通过后生成 https://glama.ai/mcp/servers/lm203688/roboparts 页面 + score badge。
# 入口：mcp-server/index.js，stdio transport（Glama 拉起容器即接管 stdin/stdout）。
# 用途：punkpeye/awesome-mcp-servers#15319 的 Glama server listing 需求（/mcp/servers/ 路径）。

FROM node:22-slim
# P0-10 修复（2026-10-26 全面审计报告）：Dockerfile 原用 node:20-slim，与
# package.json 的 engines >=22.22.0 不一致。mcp-server/package.json 的
# engines 声明为 >=18，但仓库 CI 与本地开发都已统一到 Node 22.22.x，Docker
# 用旧版会导致 Glama introspection 容器行为与本地不一致（例如 ESM flag、
# structuredClone 差异）。统一到 22-slim，与本地/CI 完全对齐。

# 非 root 用户，符合 best practice
RUN groupadd --system --gid 1001 nodejs \
 && useradd --system --uid 1001 --gid nodejs --shell /bin/sh --create-home nodejs

WORKDIR /app

# 先复制依赖声明以利用 Docker layer 缓存
COPY mcp-server/package.json mcp-server/package-lock.json* ./mcp-server/

# 安装运行时依赖（--omit=dev）
WORKDIR /app/mcp-server
RUN npm install --omit=dev --no-audit --no-fund

# 复制源码（package.json 已声明 files: index.js, dialects.js, README.md）
COPY mcp-server/index.js mcp-server/dialects.js ./

# 切到非 root
USER nodejs

# MCP server 使用 stdio transport，容器启动即接管 stdin/stdout
ENTRYPOINT ["node", "/app/mcp-server/index.js"]
