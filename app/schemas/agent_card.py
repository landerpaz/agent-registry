from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AgentExtension(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    uri: str = Field(..., alias="uri")
    description: str | None = Field(default=None, alias="description")
    required: bool | None = Field(default=None, alias="required")
    params: dict | None = Field(default=None, alias="params")


class AgentCapabilities(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    streaming: bool | None = Field(default=None, alias="streaming")
    push_notifications: bool | None = Field(default=None, alias="pushNotifications")
    extended_agent_card: bool | None = Field(default=None, alias="extendedAgentCard")
    extensions: list[AgentExtension] | None = Field(default=None, alias="extensions")


class AgentInterface(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl = Field(..., alias="url")
    protocol_binding: str = Field(
        ..., pattern=r"^(JSONRPC|GRPC|HTTP\+JSON)$", alias="protocolBinding"
    )
    tenant: str | None = Field(default=None, alias="tenant")
    protocol_version: str = Field(..., alias="protocolVersion")


class AgentProvider(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    url: HttpUrl = Field(..., alias="url")
    organization: str = Field(..., min_length=1, max_length=500, alias="organization")


class AgentSkill(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=2000)
    tags: list[str] = Field(..., min_length=1)
    examples: list[str] | None = Field(default=None)
    input_modes: list[str] | None = Field(default=None, alias="inputModes")
    output_modes: list[str] | None = Field(default=None, alias="outputModes")
    security_requirements: list[dict] | None = Field(
        default=None, alias="securityRequirements"
    )


class AgentCardCreate(BaseModel):
    """Request body for POST /agent-cards and PUT /agent-cards/{id}."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    supported_interfaces: list[AgentInterface] = Field(
        ..., min_length=1, alias="supportedInterfaces"
    )
    provider: AgentProvider | None = Field(default=None)
    version: str = Field(..., min_length=1, max_length=50)
    documentation_url: HttpUrl | None = Field(default=None, alias="documentationUrl")
    capabilities: AgentCapabilities
    security_schemes: dict | None = Field(default=None, alias="securitySchemes")
    security_requirements: list[dict] | None = Field(
        default=None, alias="securityRequirements"
    )
    default_input_modes: list[str] = Field(..., min_length=1, alias="defaultInputModes")
    default_output_modes: list[str] = Field(
        ..., min_length=1, alias="defaultOutputModes"
    )
    skills: list[AgentSkill] = Field(..., min_length=1)
    icon_url: HttpUrl | None = Field(default=None, alias="iconUrl")
    signatures: list[dict] | None = Field(default=None)


class AgentCardResponse(BaseModel):
    """Full agent card response including registry metadata."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    agent_card_id: str = Field(alias="agentCardId")
    card_data: dict = Field(alias="cardData")
    status: str
    health_status: str = Field(alias="healthStatus")
    health_checked_at: datetime | None = Field(default=None, alias="healthCheckedAt")
    created_by: str = Field(alias="createdBy")
    updated_by: str | None = Field(default=None, alias="updatedBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class OperationResponse(BaseModel):
    """Standard response for POST, PUT, DELETE operations."""

    model_config = ConfigDict(populate_by_name=True)

    agent_id: UUID | None = Field(default=None, alias="agentId")
    agent_name: str | None = Field(default=None, alias="agentName")
    agent_card_id: str | None = Field(default=None, alias="agentCardId")
    operation_status: str = Field(alias="operationStatus")  # "success" or "failed"
    error_detail: str | None = Field(default=None, alias="errorDetail")
