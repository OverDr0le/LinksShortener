from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse

from app.schemas.link import LinkCreate, LinkResponse, LinkSearchResponse, LinkUpdate, LinkStats
from app.services.link_service import LinkService, get_link_service
from app.auth.user import current_user_optional, current_user
from app.models.user import User

router = APIRouter(prefix="/links", tags=["links"])


@router.post("/shorten", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link(
    link_data: LinkCreate,
    current_user: User | None = Depends(current_user_optional),
    service: LinkService = Depends(get_link_service),
):
    try:
        link = await service.create_link(
            link_data,
            user_id=current_user.id if current_user else None
        )
        return await service.to_response(link)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{short_url}", response_model=LinkResponse)
async def update_link(
    short_url: str,
    link_data: LinkUpdate,
    current_user: User = Depends(current_user),
    service: LinkService = Depends(get_link_service)
):

    try:
        link = await service.update_link(
            short_url=short_url,
            link_data=link_data,
            current_user_id=current_user.id
        )

        return await service.to_response(link)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.delete("/{short_url}", status_code=204)
async def delete_link(
    short_url: str,
    current_user: User = Depends(current_user),
    service: LinkService = Depends(get_link_service)
):

    try:
        await service.delete_link(short_url, current_user.id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
@router.get("/{short_url}/stats", response_model=LinkStats, status_code=status.HTTP_200_OK)
async def get_stats(
    short_url: str,
    service: LinkService = Depends(get_link_service)
):

    try:
        return await service.get_stats(short_url)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.get("/by-short/{short_url}", status_code=status.HTTP_302_FOUND)
async def redirect(
    short_url: str,
    service: LinkService = Depends(get_link_service)
):

    url = await service.get_link(short_url)

    if not url:
        raise HTTPException(status_code=404, detail="Link not found")

    await service.increment_click(short_url)
    return url

@router.get("/by-original/search", response_model=LinkSearchResponse, status_code=status.HTTP_200_OK)
async def search_links(
    original_url: str = Query(..., description="Оригинальный URL для поиска короткой ссылки"),
    service: LinkService = Depends(get_link_service)
):
    link = await service.get_by_original_url(original_url)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return LinkSearchResponse(
        short_url=link.short_url,
        original_url=link.original_url,
    )
