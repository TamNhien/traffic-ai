FROM node:26.9.0-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install -g npm@12.0.2 \
    && if [ -f package-lock.json ]; then npm ci; else npm install; fi \
    && npm audit --audit-level=high
COPY . .
RUN npm run build

FROM nginx:1.31.6-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
