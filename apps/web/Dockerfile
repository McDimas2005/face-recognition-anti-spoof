FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY apps/web/package.json /app/apps/web/package.json
COPY packages/shared/package.json /app/packages/shared/package.json

COPY apps/web /app/apps/web
COPY packages/shared /app/packages/shared
RUN npm install

WORKDIR /app
CMD ["sh", "-c", "npm --workspace @face-attendance/web run build && npm --workspace @face-attendance/web run start"]
