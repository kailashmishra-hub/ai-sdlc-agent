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
