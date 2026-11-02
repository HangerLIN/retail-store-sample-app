FROM localhost:5001/bases/java@sha256:5e0092d70366ca9f8c0853768cecbc7701dde4f991198d5e8f68c9a3bab10ed7
WORKDIR /app
RUN addgroup -g 1000 app && adduser -D -u 1000 -G app app
COPY --chown=1000:1000 app.jar /app/app.jar
USER 1000:1000
ENV SPRING_PROFILES_ACTIVE=prod
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
