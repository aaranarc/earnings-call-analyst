FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN useradd --create-home --uid 10001 analyst
COPY --from=build --chown=analyst:analyst /app/.next/standalone ./
COPY --from=build --chown=analyst:analyst /app/.next/static ./.next/static
USER analyst
EXPOSE 3000
CMD ["node", "server.js"]
