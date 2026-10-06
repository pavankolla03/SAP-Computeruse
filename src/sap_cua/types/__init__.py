"""SAP-CUA types: core type definitions, Pydantic models, and schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutorType(str, Enum):
    """Available executors for SAP actions."""
    SAP_API = "sap_api"
    MCP = "mcp"
    PLAYWRIGHT = "playwright"
    GUI = "gui"
    TERMINAL = "terminal"
    CODE = "code"


class RiskLevel(str, Enum):
    """Risk classification for actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(float, Enum):
    """Confidence thresholds."""
    HIGH = 0.95
    MEDIUM = 0.75
    LOW = 0.5
    NONE = 0.0


class SAPModule(str, Enum):
    """SAP Integration Suite modules."""
    CLOUD_INTEGRATION = "Cloud Integration"
    INTEGRATION_PACKAGES = "Integration Packages"
    API_MANAGEMENT = "API Management"
    EVENT_MESH = "Event Mesh"
    MONITORING = "Monitoring"
    SECURITY_MATERIAL = "Security Material"
    DESIGN = "Design"


class Page(str, Enum):
    """Known SAP pages."""
    INTEGRATION_PACKAGES = "integration_packages"
    IFLOW_EDITOR = "iflow_editor"
    MONITOR = "monitor"
    MPL = "message_processing_logs"
    SECURITY_MATERIAL = "security_material"
    API_PROVIDER = "api_provider"
    API_PROXY = "api_proxy"
    EVENT_MESH = "event_mesh"
    DEPLOYMENT = "deployment"
    ADAPTER_CONFIG = "adapter_configuration"
    CONNECTIVITY = "connectivity"
    CREDENTIALS = "credentials"
    CREATE_PACKAGE = "create_package_dialog"
    CREATE_IFLOW = "create_iflow_dialog"
    UNKNOWN = "unknown"


class GUIActionType(str, Enum):
    """GUI action types."""
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    DRAG = "drag"
    SCROLL = "scroll"
    TYPE = "type"
    KEY_PRESS = "key_press"
    HOTKEY = "hotkey"
    WAIT = "wait"


# ─── Core Action Models ───────────────────────────────────────────────────────

class GUIAction(BaseModel):
    """A GUI-level action with normalized coordinates."""
    type: GUIActionType
    x: float | None = Field(None, ge=0.0, le=1.0, description="Normalized x coordinate (0-1)")
    y: float | None = Field(None, ge=0.0, le=1.0, description="Normalized y coordinate (0-1)")
    x2: float | None = Field(None, ge=0.0, le=1.0, description="End x for drag")
    y2: float | None = Field(None, ge=0.0, le=1.0, description="End y for drag")
    text: str | None = Field(None, description="Text to type")
    key: str | None = Field(None, description="Key for key_press/hotkey")
    keys: list[str] | None = Field(None, description="Keys for hotkey combo")
    duration_ms: int | None = Field(None, ge=0, description="Wait duration in ms")


class SAPAction(BaseModel):
    """A structured SAP action with semantic meaning."""
    intent: str = Field(..., description="Semantic action identifier")
    executor: ExecutorType = Field(..., description="Preferred executor")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Typed arguments")
    gui_action: GUIAction | None = Field(None, description="GUI action if executor is gui")
    fallback_executor: ExecutorType | None = Field(None, description="Fallback if primary fails")
    risk: RiskLevel = Field(RiskLevel.LOW)
    expected_state: str = Field(..., description="Expected post-action state")
    requires_approval: bool = Field(False, description="Whether human approval is needed")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    reasoning: str | None = Field(None, description="Brief decision summary")


class ActionResult(BaseModel):
    """Result of executing an SAP action."""
    action: SAPAction
    success: bool
    observed_state: str = Field(..., description="Actual post-action state")
    verification: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int = Field(0, ge=0)
    screenshot_before: str | None = None
    screenshot_after: str | None = None


class SAPState(BaseModel):
    """Current state of the SAP environment."""
    module: SAPModule | None = None
    page: Page = Page.UNKNOWN
    resolution: tuple[int, int] = Field(default=(1440, 900))
    url: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskDefinition(BaseModel):
    """A SAP task definition."""
    task_id: str
    instruction: str
    module: SAPModule | None = None
    difficulty: int = Field(1, ge=1, le=5)
    setup: dict[str, Any] | None = None
    verify: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)


class Trajectory(BaseModel):
    """A complete agent trajectory for training/evaluation."""
    task_id: str
    task: str
    environment: dict[str, Any]
    steps: list[dict[str, Any]]
    final_verification: dict[str, Any]
    success: bool
    actions_count: int = 0
    duration_ms: int = 0
    model: str | None = None
    checkpoint: str | None = None


class BenchmarkResult(BaseModel):
    """Result from running a benchmark task."""
    task_id: str
    model: str
    run_id: str
    success: bool
    steps_taken: int
    max_steps: int
    duration_ms: int
    actions: list[SAPAction]
    trajectory: Trajectory | None = None
    error: str | None = None
    cost_usd: float = 0.0


class ModelRequest(BaseModel):
    """Request to the model inference."""
    image_paths: list[str]
    instruction: str
    history: list[dict[str, Any]] | None = None
    sap_state: SAPState | None = None
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(512, ge=1, le=4096)


class ModelResponse(BaseModel):
    """Response from the model inference."""
    intent: str
    executor: ExecutorType
    arguments: dict[str, Any] = Field(default_factory=dict)
    gui_action: GUIAction | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    raw_output: str | None = None


class SecretMatch(BaseModel):
    """Detected secret in text."""
    secret_type: str
    match: str
    replacement: str
    line: int | None = None
    column: int | None = None
