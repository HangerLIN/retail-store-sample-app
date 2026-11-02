FROM docker.io/library/amazoncorretto:21-alpine@sha256:4671567c1e0f43f93366a0a76fabbba6e9463c5448058e54fcc0c643830b2e5b
WORKDIR /app
RUN addgroup -g 1000 app && adduser -D -u 1000 -G app app
COPY --chown=1000:1000 app.jar /app/app.jar
USER 1000:1000
ENV SPRING_PROFILES_ACTIVE=prod
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
