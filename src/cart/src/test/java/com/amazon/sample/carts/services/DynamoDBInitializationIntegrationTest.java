package com.amazon.sample.carts.services;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BillingMode;
import software.amazon.awssdk.services.dynamodb.model.KeyType;
import software.amazon.awssdk.services.dynamodb.model.ScalarAttributeType;

@Testcontainers
@Tag("integration")
class DynamoDBInitializationIntegrationTest {

  @Container
  static DynamoDBContainer database = new DynamoDBContainer(
    DockerImageName.parse("amazon/dynamodb-local:1.20.0")
  );

  private DynamoDbClient client() {
    return DynamoDbClient.builder()
      .endpointOverride(
        URI.create(
          "http://" + database.getHost() + ":" + database.getMappedPort(8000)
        )
      )
      .region(Region.US_EAST_1)
      .credentialsProvider(
        StaticCredentialsProvider.create(
          AwsBasicCredentials.create("test", "test")
        )
      )
      .build();
  }

  private DynamoDBCartService service(DynamoDbClient client, String name) {
    return new DynamoDBCartService(
      client,
      DynamoDbEnhancedClient.builder().dynamoDbClient(client).build(),
      true,
      name
    );
  }

  @Test
  void missingTableIsCreatedWithUsableGsi() {
    String name = "init-" + UUID.randomUUID();
    try (var client = client()) {
      var carts = service(client, name);
      carts.init();
      carts.add("first", "product", 1, 150);
      assertEquals(1, carts.items("first").size());
    }
  }

  @Test
  void repeatedInitializationPreservesExistingCart() {
    String name = "init-" + UUID.randomUUID();
    try (var client = client()) {
      var first = service(client, name);
      first.init();
      first.add("survivor", "product", 1, 150);
      var restarted = service(client, name);
      restarted.init();
      assertEquals(1, restarted.items("survivor").size());
      assertEquals("product", restarted.items("survivor").get(0).getItemId());
      assertEquals(150, restarted.items("survivor").get(0).getUnitPrice());
    }
  }

  @Test
  void concurrentInitializersKeepOneUsableTable() throws Exception {
    String name = "init-" + UUID.randomUUID();
    try (
      var client = client();
      var executor = java.util.concurrent.Executors.newFixedThreadPool(2)
    ) {
      var start = new java.util.concurrent.CountDownLatch(1);
      var first = executor.submit(() -> {
        start.await();
        service(client, name).init();
        return true;
      });
      var second = executor.submit(() -> {
        start.await();
        service(client, name).init();
        return true;
      });
      start.countDown();
      assertTrue(first.get(40, java.util.concurrent.TimeUnit.SECONDS));
      assertTrue(second.get(40, java.util.concurrent.TimeUnit.SECONDS));
      var carts = service(client, name);
      carts.add("concurrent", "product", 1, 150);
      assertEquals(1, carts.items("concurrent").size());
    }
  }

  @Test
  void missingGsiFailsWithoutDeletingExistingData() {
    String name = "init-" + UUID.randomUUID();
    try (var client = client()) {
      client.createTable(b ->
        b
          .tableName(name)
          .attributeDefinitions(a ->
            a.attributeName("id").attributeType(ScalarAttributeType.S)
          )
          .keySchema(k -> k.attributeName("id").keyType(KeyType.HASH))
          .billingMode(BillingMode.PAY_PER_REQUEST)
      );
      var key = Map.of("id", AttributeValue.fromS("keep-me"));
      client.putItem(b -> b.tableName(name).item(key));
      var failure = assertThrows(IllegalStateException.class, () ->
        service(client, name).init()
      );
      assertTrue(failure.getMessage().contains("refusing to delete data"));
      assertEquals(
        "keep-me",
        client
          .getItem(b -> b.tableName(name).key(key))
          .item()
          .get("id")
          .s()
      );
    }
  }
}
