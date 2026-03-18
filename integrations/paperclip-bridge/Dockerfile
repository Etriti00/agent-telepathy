FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install --frozen-lockfile

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build

EXPOSE 8101 3001

CMD ["node", "dist/index.js"]
