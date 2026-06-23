# ============ 第一阶段：构建前端 ============
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖
COPY package*.json ./
RUN npm install

# 复制源代码
COPY . .

# 构建生产版本
# VITE_API_BASE_URL 是前端构建时用的环境变量
# 在 Docker 中运行时通过 nginx 反向代理，所以设为空
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ============ 第二阶段：运行 Nginx ============
FROM nginx:alpine

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制上传目录（挂载点）
RUN mkdir -p /app/uploads && chown -R nginx:nginx /usr/share/nginx/html && chown -R nginx:nginx /app/uploads

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
