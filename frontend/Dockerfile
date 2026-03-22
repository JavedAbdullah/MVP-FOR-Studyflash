FROM node:20-alpine

WORKDIR /app

# Install deps first for caching
COPY frontend/package.json frontend/package-lock.json* /app/
RUN npm ci || npm install

# Copy app source
COPY frontend /app

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
