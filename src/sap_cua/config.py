"""SAP-CUA configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_env_file(path: Path) -> dict[str, str]:
    """Load a .env file into a dict."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


class SAPConfig(BaseSettings):
    """SAP tenant configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    environment: str = "sandbox"
    base_url: str = "https://tenant.integration.cloud.sap"
    api_base_url: str = "https://tenant.integration.cloud.sap/api/v1"
    client_id: str = ""
    client_secret: str = ""
    user: str = ""
    password: str = ""
    token_endpoint: str = ""

    @model_validator(mode="after")
    def _validate_credentials(self) -> "SAPConfig":
        if self.environment == "production" and not self.client_id:
            raise ValueError("SAP_CLIENT_ID required for production")
        return self


class ModelConfig(BaseSettings):
    """Model inference configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    base_path: str = "sap-cua-7b-v0"
    use_vllm: bool = False
    vllm_gpu_memory_utilization: float = 0.9
    inference_device: str = "cpu"
    torch_dtype: str = "float32"
    max_image_tokens: int = 1024
    max_text_tokens: int = 512


class TrainingConfig(BaseSettings):
    """Training configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    train_batch_size: int = 4
    eval_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    num_epochs: int = 3
    warmup_steps: int = 100
    save_steps: int = 500
    logging_steps: int = 10
    max_grad_norm: float = 1.0
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    use_qlora: bool = True
    quantization_bits: int = 4
    deepspeed_config: str = "configs/ds_zero2.json"


class APIConfig(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    cors_origins: str = "http://localhost:3000"


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    url: str = "postgresql+asyncpg://sapcua:changeme@localhost:5432/sapcua"
    echo: bool = False


class RedisConfig(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    url: str = "redis://localhost:6379/0"


class StorageConfig(BaseSettings):
    """Object storage configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "sapcua-artifacts"


class SecurityConfig(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    secret_redaction_enabled: bool = True
    audit_log_level: str = "INFO"
    destructive_action_require_approval: bool = True


class CostConfig(BaseSettings):
    """Cost governance configuration."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    max_job_cost_usd: float = 50.0
    cost_tracking_enabled: bool = True


class Config(BaseSettings):
    """Root configuration combining all sub-configs."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    sap: SAPConfig = Field(default_factory=SAPConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cost: CostConfig = Field(default_factory=CostConfig)

    @classmethod
    def load(cls) -> "Config":
        """Load config from .env files and environment."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        env_local = project_root / ".env.local"
        env_file = project_root / ".env"
        env_example = project_root / ".env.example"

        for env_path in (env_local, env_file, env_example):
            if env_path.exists():
                env_vars = _load_env_file(env_path)
                for key, value in env_vars.items():
                    os.environ.setdefault(key, value)
                break
        try:
            return cls()
        except ValidationError as exc:
            raise SystemExit(f"Configuration error:\n{exc}") from exc


# Global config instance
config = Config.load()
