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
