from app.models.survey import Well
from sqlmodel import Session, select

def create_well(well: Well, session: Session):
    session.add(well)
    session.commit()
    return well

def get_well(operator_id: int, session: Session) -> Well | None:
    return session.exec(select(Well).where(Well.operator_id == operator_id)).all()

def get_all_wells(session: Session) -> list[Well]:
    return session.exec(select(Well)).all()

def create_well(well: Well, session: Session) -> Well:
    session.add(well)
    session.commit()
    return well
    
def update_well(well: Well, session: Session) -> Well:
    session.add(well)
    session.commit()
    return well

def delete_well(well: Well, session: Session) -> Well:
    session.delete(well)
    session.commit()
    return well