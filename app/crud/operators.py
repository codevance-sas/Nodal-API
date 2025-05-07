from app.models.survey import Operator
from sqlmodel import Session, select

def create_operator(operator: Operator, session: Session):
    session.add(operator)
    session.commit()
    return operator

def get_operator(operator_id: int, session: Session) -> Operator | None:
    return session.exec(select(Operator).where(Operator.id == operator_id)).first()

def get_all_operators(session: Session) -> list[Operator]:
    return session.exec(select(Operator)).all()

def create_operator(operator: Operator, session: Session) -> Operator:
    session.add(operator)
    session.commit()
    return operator
    
def update_operator(operator: Operator, session: Session) -> Operator:
    session.add(operator)
    session.commit()
    return operator

def delete_operator(operator: Operator, session: Session) -> Operator:
    session.delete(operator)
    session.commit()
    return operator