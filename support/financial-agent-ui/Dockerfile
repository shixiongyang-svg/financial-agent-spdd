FROM node:20-alpine

# Create non-root user
RUN addgroup -g 1001 -S appuser && adduser -u 1001 -S appuser -G appuser

WORKDIR /app

# Copy dependency files first for layer caching
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application source
COPY public/ ./public/
COPY src/ ./src/

# Switch to non-root user
USER appuser

EXPOSE 3000

CMD ["npx", "serve", "public", "-l", "3000"]
