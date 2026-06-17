# Automation Framework

## automation/pom.xml

```text
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.generated.automation</groupId>
  <artifactId>rest-assured-automation</artifactId>
  <version>1.0.0</version>
  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <junit.jupiter.version>5.10.3</junit.jupiter.version>
    <rest.assured.version>5.5.0</rest.assured.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>io.rest-assured</groupId>
      <artifactId>rest-assured</artifactId>
      <version>${rest.assured.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>${junit.jupiter.version}</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.3.1</version>
      </plugin>
    </plugins>
  </build>
</project>

```

## automation/src/test/java/config/AutomationConfig.java

```java
package config;

public final class AutomationConfig {
  private AutomationConfig() {}

  public static String baseUri() {
    return System.getProperty("baseUri", "http://localhost:8080");
  }

  public static String recordsPath() {
    return "/api/records";
  }
}

```

## automation/src/test/java/api/ApiClient.java

```java
package api;

import config.AutomationConfig;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

import static io.restassured.RestAssured.given;

public class ApiClient {
  public Response getRecords() {
    return baseRequest().get(AutomationConfig.recordsPath());
  }

  public Response createRecord(String requestBody) {
    return baseRequest().body(requestBody).post(AutomationConfig.recordsPath());
  }

  private RequestSpecification baseRequest() {
    return given()
        .baseUri(AutomationConfig.baseUri())
        .contentType("application/json")
        .accept("application/json");
  }
}

```

## automation/src/test/java/utils/RequestBuilder.java

```java
package utils;

public final class RequestBuilder {
  private RequestBuilder() {}

  public static String validRecordPayload() {
    return "{" +
        "\"name\":\"sample-record\"," +
        "\"description\":\"created from Rest Assured automation\"" +
        "}";
  }

  public static String invalidRecordPayload() {
    return "{" +
        "\"description\":\"missing mandatory name\"" +
        "}";
  }
}

```

## automation/src/test/java/tests/BaseTest.java

```java
package tests;

import api.ApiClient;
import org.junit.jupiter.api.BeforeEach;

public abstract class BaseTest {
  protected ApiClient apiClient;

  @BeforeEach
  void setUp() {
    apiClient = new ApiClient();
  }
}

```

## automation/src/test/java/tests/RecordApiTest.java

```java
package tests;

import io.restassured.response.Response;
import org.junit.jupiter.api.Test;
import utils.RequestBuilder;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.*;

public class RecordApiTest extends BaseTest {
  @Test
  void createRecordSuccessfully() {
    Response response = apiClient.createRecord(RequestBuilder.validRecordPayload());

    assertThat(response.statusCode(), is(anyOf(equalTo(200), equalTo(201))));
    assertThat(response.jsonPath().getString("name"), is("sample-record"));
  }

  @Test
  void rejectInvalidRecordPayload() {
    Response response = apiClient.createRecord(RequestBuilder.invalidRecordPayload());

    assertThat(response.statusCode(), is(anyOf(equalTo(400), equalTo(422))));
  }

  @Test
  void listRecordsSuccessfully() {
    Response response = apiClient.getRecords();

    assertThat(response.statusCode(), is(200));
  }
}

```