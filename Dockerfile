# RoboParts MCP Server — Dockerfile for Glama server introspection
# Glama 会自动扫描仓库根目录的 Dockerfile 并拉起容器做 MCP 握手检查。
# 入口点：mcp-server/index.js，使用 stdio transport。
# 详见 https://glama.ai/mcp/servers — 提交后 URL 形如 /mcp/servers/lm203688/roboparts

FROM node:20-slim

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
