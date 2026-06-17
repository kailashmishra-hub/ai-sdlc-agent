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
