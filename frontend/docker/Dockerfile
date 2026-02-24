FROM node:20-alpine AS builder

WORKDIR /app

# Copy frontend package files
COPY package*.json .

# Install dependencies
RUN npm install

# Copy frontend source
COPY . .

# Build frontend
RUN npm run build

FROM nginx:alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]