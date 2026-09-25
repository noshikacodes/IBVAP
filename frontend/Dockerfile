# ==============================================================================
# IBVAP Frontend - Multi-Stage Production Dockerfile (React + Vite + Nginx)
# ==============================================================================

# Stage 1: Build production static bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors and install dependencies
COPY frontend/package.json ./
RUN npm install

# Copy source code and build Vite production bundle
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve static bundle via Nginx
FROM nginx:alpine

# Remove default Nginx site configuration
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom Nginx reverse proxy configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy production assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
