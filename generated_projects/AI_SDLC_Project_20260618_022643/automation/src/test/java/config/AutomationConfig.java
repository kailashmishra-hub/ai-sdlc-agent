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
