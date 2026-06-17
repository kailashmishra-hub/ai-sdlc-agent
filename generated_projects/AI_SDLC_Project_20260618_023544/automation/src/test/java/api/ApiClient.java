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
