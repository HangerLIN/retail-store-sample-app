FROM docker.io/library/node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914
WORKDIR /app
COPY --chown=node:node dist ./dist
COPY --chown=node:node node_modules ./node_modules
USER node
ENTRYPOINT ["node", "dist/main.js"]
