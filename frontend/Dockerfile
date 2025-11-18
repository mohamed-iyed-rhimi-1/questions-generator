# Multi-stage Dockerfile for React frontend
# Stage 1: Base - shared dependencies
FROM node:18-alpine AS base

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Stage 2: Development - full tooling with hot-reload
FROM base AS development

# Install all dependencies including devDependencies
RUN npm ci

# Copy all source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start development server with host binding for external access
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Stage 3: Build - production build
FROM base AS build

# Install all dependencies
RUN npm ci

# Copy source code
COPY . .

# Declare build argument for API URL
ARG VITE_API_URL=http://localhost:8000

# Set environment variable for Vite build
ENV VITE_API_URL=$VITE_API_URL

# Build the application (outputs to dist/)
RUN npm run build

# Stage 4: Production - serve with nginx
FROM nginx:alpine AS production

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
