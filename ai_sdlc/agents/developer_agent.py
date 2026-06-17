from __future__ import annotations

import json
from typing import Any

from ai_sdlc.config import AppConfig
from ai_sdlc.llm import LLMClient


class DeveloperAgent:
    JAVA_REQUIRED_FILES = [
        "pom.xml",
        "src/main/resources/application.yml",
        "src/main/java/com/generated/AiSdlcApplication.java",
        "src/main/java/com/generated/controller/RecordController.java",
        "src/main/java/com/generated/service/RecordService.java",
        "src/main/java/com/generated/service/impl/RecordServiceImpl.java",
        "src/main/java/com/generated/repository/RecordRepository.java",
        "src/main/java/com/generated/entity/RecordEntity.java",
        "src/main/java/com/generated/dto/RecordRequest.java",
        "src/main/java/com/generated/dto/RecordResponse.java",
        "src/main/java/com/generated/exception/GlobalExceptionHandler.java",
        "src/main/java/com/generated/config/OpenApiConfig.java",
        "openapi.yml",
    ]

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, requirement_spec: dict[str, Any], ba_output: dict[str, Any], bdd: str, config: AppConfig) -> dict[str, str]:
        system = (
            "You are DeveloperAgent for an AI SDLC platform. "
            "Generate complete compilable application source code. "
            "Return only valid JSON mapping relative file paths to file contents."
        )
        user = f"""
Generate complete application source code.

Selected Technology Stack: {config.technology_stack}

Input artifacts:
- Requirement Specification
- User Stories
- Acceptance Criteria
- BDD Scenarios

For Java based projects, generate:
- Controllers
- Services
- Service Implementations
- Repositories
- Entities
- DTOs
- Exception Handlers
- Configuration Classes
- application.yml
- pom.xml
- OpenAPI Specification

Output must be complete compilable source code as JSON:
{{
  "relative/path/File.ext": "file content"
}}

Requirements:
{json.dumps(requirement_spec, indent=2)}

BA output:
{json.dumps(ba_output, indent=2)}

BDD:
{bdd}
"""
        response = self.llm.invoke_json(system, user)
        if self._is_valid_source_map(response, config):
            return response
        return self._fallback_java() if config.technology_stack == "Java" else self._fallback_python()

    def _is_valid_source_map(self, response: Any, config: AppConfig) -> bool:
        if not isinstance(response, dict):
            return False
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in response.items()):
            return False
        if config.technology_stack == "Java":
            return all(path in response for path in self.JAVA_REQUIRED_FILES)
        return True

    def _fallback_java(self) -> dict[str, str]:
        return {
            "pom.xml": """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.generated</groupId>
  <artifactId>ai-sdlc-app</artifactId>
  <version>1.0.0</version>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.2</version>
    <relativePath/>
  </parent>
  <properties>
    <java.version>17</java.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springdoc</groupId>
      <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
      <version>2.6.0</version>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
""",
            "src/main/resources/application.yml": "server:\n  port: 8080\nspring:\n  application:\n    name: ai-sdlc-app\n",
            "src/main/java/com/generated/AiSdlcApplication.java": """package com.generated;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class AiSdlcApplication {
  public static void main(String[] args) {
    SpringApplication.run(AiSdlcApplication.class, args);
  }
}
""",
            "src/main/java/com/generated/controller/RecordController.java": """package com.generated.controller;

import com.generated.dto.RecordRequest;
import com.generated.dto.RecordResponse;
import com.generated.service.RecordService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/records")
public class RecordController {
  private final RecordService recordService;

  public RecordController(RecordService recordService) {
    this.recordService = recordService;
  }

  @GetMapping
  public List<RecordResponse> list() {
    return recordService.list();
  }

  @PostMapping
  public RecordResponse create(@Valid @RequestBody RecordRequest request) {
    return recordService.create(request);
  }
}
""",
            "src/main/java/com/generated/service/RecordService.java": """package com.generated.service;

import com.generated.dto.RecordRequest;
import com.generated.dto.RecordResponse;
import java.util.List;

public interface RecordService {
  List<RecordResponse> list();
  RecordResponse create(RecordRequest request);
}
""",
            "src/main/java/com/generated/service/impl/RecordServiceImpl.java": """package com.generated.service.impl;

import com.generated.dto.RecordRequest;
import com.generated.dto.RecordResponse;
import com.generated.entity.RecordEntity;
import com.generated.repository.RecordRepository;
import com.generated.service.RecordService;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class RecordServiceImpl implements RecordService {
  private final RecordRepository recordRepository;

  public RecordServiceImpl(RecordRepository recordRepository) {
    this.recordRepository = recordRepository;
  }

  public List<RecordResponse> list() {
    return recordRepository.findAll().stream().map(this::toResponse).toList();
  }

  public RecordResponse create(RecordRequest request) {
    RecordEntity entity = new RecordEntity(recordRepository.nextId(), request.name(), request.description());
    recordRepository.save(entity);
    return toResponse(entity);
  }

  private RecordResponse toResponse(RecordEntity entity) {
    return new RecordResponse(entity.id(), entity.name(), entity.description(), "created");
  }
}
""",
            "src/main/java/com/generated/repository/RecordRepository.java": """package com.generated.repository;

import com.generated.entity.RecordEntity;
import org.springframework.stereotype.Repository;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

@Repository
public class RecordRepository {
  private final List<RecordEntity> records = new ArrayList<>();
  private final AtomicLong sequence = new AtomicLong(1);

  public List<RecordEntity> findAll() {
    return List.copyOf(records);
  }

  public RecordEntity save(RecordEntity entity) {
    records.add(entity);
    return entity;
  }

  public Long nextId() {
    return sequence.getAndIncrement();
  }
}
""",
            "src/main/java/com/generated/entity/RecordEntity.java": """package com.generated.entity;

public record RecordEntity(Long id, String name, String description) {}
""",
            "src/main/java/com/generated/dto/RecordRequest.java": """package com.generated.dto;

import jakarta.validation.constraints.NotBlank;

public record RecordRequest(
    @NotBlank(message = "name is required") String name,
    String description
) {}
""",
            "src/main/java/com/generated/dto/RecordResponse.java": """package com.generated.dto;

public record RecordResponse(Long id, String name, String description, String status) {}
""",
            "src/main/java/com/generated/exception/GlobalExceptionHandler.java": """package com.generated.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestControllerAdvice
public class GlobalExceptionHandler {
  @ResponseStatus(HttpStatus.BAD_REQUEST)
  @ExceptionHandler(MethodArgumentNotValidException.class)
  public Map<String, Object> handleValidation(MethodArgumentNotValidException ex) {
    List<String> errors = ex.getBindingResult().getFieldErrors().stream()
        .map(error -> error.getField() + ": " + error.getDefaultMessage())
        .toList();
    return Map.of("status", "validation_failed", "errors", errors);
  }

  @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
  @ExceptionHandler(Exception.class)
  public Map<String, String> handle(Exception ex) {
    return Map.of("status", "error", "message", ex.getMessage());
  }
}
""",
            "src/main/java/com/generated/config/OpenApiConfig.java": """package com.generated.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {
  @Bean
  public OpenAPI generatedOpenApi() {
    return new OpenAPI().info(new Info().title("Generated AI SDLC API").version("1.0.0"));
  }
}
""",
            "openapi.yml": """openapi: 3.0.3
info:
  title: Generated AI SDLC API
  version: 1.0.0
paths:
  /api/records:
    get:
      summary: List records
      responses:
        '200':
          description: Records returned
    post:
      summary: Create record
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RecordRequest'
      responses:
        '200':
          description: Record created
components:
  schemas:
    RecordRequest:
      type: object
      required: [name]
      properties:
        name:
          type: string
        description:
          type: string
    RecordResponse:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
        description:
          type: string
        status:
          type: string
""",
        }

    def _fallback_python(self) -> dict[str, str]:
        return {
            "README.md": "# Generated Python Application\n\nRun with `uvicorn src.main:app --reload`.\n",
            "requirements.txt": "fastapi\nuvicorn\npydantic\npytest\n",
            "src/main.py": """from fastapi import FastAPI
from src.schemas import Record
from src.service import RecordService

app = FastAPI(title="Generated AI SDLC API")
service = RecordService()

@app.get("/api/records")
def list_records():
    return service.list_records()

@app.post("/api/records")
def create_record(record: Record):
    return service.create_record(record)
""",
            "src/schemas.py": """from pydantic import BaseModel

class Record(BaseModel):
    name: str
    description: str | None = None
""",
            "src/service.py": """from src.repository import RecordRepository
from src.schemas import Record

class RecordService:
    def __init__(self):
        self.repository = RecordRepository()

    def list_records(self):
        return self.repository.list_records()

    def create_record(self, record: Record):
        return self.repository.create_record(record)
""",
            "src/repository.py": """class RecordRepository:
    def __init__(self):
        self.records = []

    def list_records(self):
        return self.records

    def create_record(self, record):
        payload = record.model_dump()
        self.records.append(payload)
        return {"status": "created", "record": payload}
""",
            "tests/test_api.py": """from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_create_record():
    response = client.post("/api/records", json={"name": "sample"})
    assert response.status_code == 200
    assert response.json()["status"] == "created"
""",
        }
