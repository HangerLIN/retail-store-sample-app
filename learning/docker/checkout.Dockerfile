FROM localhost:5001/bases/checkout@sha256:1da33afdf94a4ccf4a862836c7ca77ba0d7a0900ade96fb2c3c35c5d1dce208e
WORKDIR /app
COPY --chown=node:node dist ./dist
COPY --chown=node:node node_modules ./node_modules
USER node
ENTRYPOINT ["node", "dist/main.js"]
