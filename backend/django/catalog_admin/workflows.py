import sys
from pathlib import Path


FASTAPI_DIRECTORY = Path(__file__).resolve().parents[2] / 'fastapi'
if str(FASTAPI_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(FASTAPI_DIRECTORY))

from dotenv import load_dotenv

load_dotenv(FASTAPI_DIRECTORY / '.env')

from database import SessionLocal, engine
import models as fastapi_models
from order_status_service import (
    OrderStatusTransitionError,
    transition_order_status,
)


engine.echo = False


def update_order_status(order_id, status):
    session = SessionLocal()
    try:
        order = session.query(fastapi_models.Order).filter(
            fastapi_models.Order.id == order_id
        ).with_for_update().first()
        if order is None:
            raise OrderStatusTransitionError(404, 'Order not found')
        return transition_order_status(session, order, status)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()