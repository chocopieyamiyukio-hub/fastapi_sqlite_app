from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from controllers import item_controller
from models.db_models import Item
from models.schemas import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter(prefix="/items", tags=["Items"])


@router.post(
    "/",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
) -> Item:
    """Create a new item."""
    return item_controller.create_item(db=db, item_data=item_data)


@router.get("/", response_model=list[ItemResponse])
def read_items(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Item]:
    """List items with pagination."""
    return item_controller.get_items(db=db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=ItemResponse)
def read_item(
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Item:
    """Get a single item by ID."""
    return item_controller.get_item_by_id(db=db, item_id=item_id)


@router.patch("/{item_id}", response_model=ItemResponse)
def patch_item(
    item_data: ItemUpdate,
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Item:
    """Partially update an existing item."""
    return item_controller.update_item(
        db=db, item_id=item_id, item_data=item_data, exclude_unset=True
    )


@router.put("/{item_id}", response_model=ItemResponse)
def replace_item(
    item_data: ItemCreate,
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Item:
    """Replace all fields of an existing item."""
    return item_controller.update_item(
        db=db, item_id=item_id, item_data=item_data, exclude_unset=False
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> None:
    """Delete an item by ID."""
    item_controller.delete_item(db=db, item_id=item_id)
