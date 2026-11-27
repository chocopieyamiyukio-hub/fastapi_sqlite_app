from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.db_models import Item
from models.schemas import ItemCreate, ItemUpdate


def get_items(db: Session, skip: int = 0, limit: int = 100) -> list[Item]:
    """Retrieve a paginated list of items ordered by ID."""
    stmt = select(Item).order_by(Item.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_item_by_id(db: Session, item_id: int) -> Item:
    """Retrieve a single item by ID or raise 404."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return item


def create_item(db: Session, item_data: ItemCreate) -> Item:
    """Create and persist a new item."""
    new_item = Item(**item_data.model_dump())
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def update_item(
    db: Session,
    item_id: int,
    item_data: ItemUpdate | ItemCreate,
    *,
    exclude_unset: bool = True,
) -> Item:
    """Update fields on an existing item (partial for PATCH, full for PUT)."""
    item = get_item_by_id(db, item_id)
    updates = item_data.model_dump(exclude_unset=exclude_unset)
    if not updates:
        return item

    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    """Delete an item by ID."""
    item = get_item_by_id(db, item_id)
    db.delete(item)
    db.commit()
