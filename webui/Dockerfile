FROM node:18-alpine


WORKDIR /app

COPY webui/package*.json ./

RUN npm install --legacy-peer-deps

EXPOSE 3000

COPY webui .
CMD ["npm", "start"]