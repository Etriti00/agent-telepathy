FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY dist/ ./dist/

# Plugin script for xyops to invoke
COPY plugin/ ./plugin/

EXPOSE 3002

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD wget -q --spider http://localhost:3002/health || exit 1

CMD ["node", "dist/index.js"]
