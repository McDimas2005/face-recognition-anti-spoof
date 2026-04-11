FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared/package.json ./packages/shared/package.json

RUN npm install

COPY apps/web ./apps/web
COPY packages/shared ./packages/shared

CMD ["sh", "-c", "npm --workspace @face-attendance/web run build && npm --workspace @face-attendance/web run start"]
