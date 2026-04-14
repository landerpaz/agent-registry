import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession, OptionalUser, Publisher
from app.schemas.agent_card import AgentCardCreate, AgentCardResponse, OperationResponse
from app.schemas.common import PaginatedResponse
from app.services import agent_card_service as svc

router = APIRouter(prefix="/agent-cards", tags=["Agent Cards"])


# ---------------------------------------------------------------------------
# Write endpoints (auth required)
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=OperationResponse,
    response_model_by_alias=True,
)
async def create_agent_card(
    payload: AgentCardCreate,
    session: DBSession,
    current_user: CurrentUser,
    publisher: Publisher,
) -> OperationResponse:
    result = await svc.create_agent_card(session, payload, current_user)

    if result.operation_status == "success" and result.agent_id:
        card = await svc.get_agent_card_by_id(session, result.agent_id)
        if card:
            await publisher.publish(
                "agent_card_created",
                result.agent_id,
                result.agent_name,
                result.agent_card_id,
                card.card_data,
            )

    return result


@router.put(
    "/{agent_id}",
    response_model=OperationResponse,
    response_model_by_alias=True,
)
async def update_agent_card(
    agent_id: uuid.UUID,
    payload: AgentCardCreate,
    session: DBSession,
    current_user: CurrentUser,
    publisher: Publisher,
) -> OperationResponse:
    result = await svc.update_agent_card(session, agent_id, payload, current_user)

    if result.operation_status == "failed":
        error = result.error_detail or ""
        if "not found" in error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        if "Forbidden" in error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)

    if result.operation_status == "success" and result.agent_id:
        card = await svc.get_agent_card_by_id(session, result.agent_id)
        if card:
            await publisher.publish(
                "agent_card_updated",
                result.agent_id,
                result.agent_name,
                result.agent_card_id,
                card.card_data,
            )

    return result


@router.delete(
    "/{agent_id}",
    response_model=OperationResponse,
    response_model_by_alias=True,
)
async def delete_agent_card(
    agent_id: uuid.UUID,
    session: DBSession,
    current_user: CurrentUser,
    publisher: Publisher,
) -> OperationResponse:
    result = await svc.delete_agent_card(session, agent_id, current_user)

    if result.operation_status == "failed":
        error = result.error_detail or ""
        if "not found" in error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
        if "Forbidden" in error:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)

    if result.operation_status == "success" and result.agent_id:
        await publisher.publish(
            "agent_card_deleted",
            result.agent_id,
            result.agent_name,
            result.agent_card_id,
        )

    return result


# ---------------------------------------------------------------------------
# Read endpoints (auth optional)
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=AgentCardResponse,
    response_model_by_alias=True,
)
async def search_agent_cards(
    session: DBSession,
    _user: OptionalUser,
    name: Annotated[str | None, Query(description="Agent name")] = None,
    version: Annotated[
        str | None, Query(description="Exact version (requires name)")
    ] = None,
) -> AgentCardResponse:
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'name' is required",
        )
    card = await svc.search_agent_cards(session, name, version)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return card


@router.get(
    "/by-slug/{agent_card_id}/versions",
    response_model=list[AgentCardResponse],
    response_model_by_alias=True,
)
async def list_versions_by_slug(
    agent_card_id: str,
    session: DBSession,
    _user: OptionalUser,
) -> list[AgentCardResponse]:
    versions = await svc.get_all_versions_by_slug(session, agent_card_id)
    if not versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return versions


@router.get(
    "/by-slug/{agent_card_id}",
    response_model=AgentCardResponse,
    response_model_by_alias=True,
)
async def get_latest_by_slug(
    agent_card_id: str,
    session: DBSession,
    _user: OptionalUser,
) -> AgentCardResponse:
    card = await svc.get_latest_by_slug(session, agent_card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return card


@router.get(
    "",
    response_model=PaginatedResponse[AgentCardResponse],
    response_model_by_alias=True,
)
async def list_agent_cards(
    session: DBSession,
    _user: OptionalUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> PaginatedResponse[AgentCardResponse]:
    return await svc.list_agent_cards(session, page, page_size, status_filter)


@router.get(
    "/{agent_id}",
    response_model=AgentCardResponse,
    response_model_by_alias=True,
)
async def get_agent_card_by_id(
    agent_id: uuid.UUID,
    session: DBSession,
    _user: OptionalUser,
) -> AgentCardResponse:
    card = await svc.get_agent_card_by_id(session, agent_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return card
