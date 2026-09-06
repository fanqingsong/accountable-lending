FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/node:22-alpine AS build
WORKDIR /app
ENV NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
COPY lending/package.json lending/package-lock.json ./
RUN npm ci
COPY lending/ ./
ARG VITE_LENDING_API_BASE=
ARG VITE_LENDING_EXPLORER_URL=http://localhost:8000
ENV VITE_LENDING_API_BASE=$VITE_LENDING_API_BASE
ENV VITE_LENDING_EXPLORER_URL=$VITE_LENDING_EXPLORER_URL
RUN npm run build

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html/lending
COPY nginx.conf /etc/nginx/conf.d/default.conf
