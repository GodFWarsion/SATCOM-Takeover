FROM node:18-alpine
WORKDIR /app
COPY webui/package*.json ./
RUN npm install --legacy-peer-deps
COPY webui .

ENV HOST 0.0.0.0
EXPOSE 3000

CMD ["npm", "start"]
