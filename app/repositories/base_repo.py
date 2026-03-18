from sqlalchemy.orm import Session

class BaseRepository:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id