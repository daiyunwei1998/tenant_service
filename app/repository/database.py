from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import settings

Base = declarative_base()

class TenantDoc(Base):
    __tablename__ = 'tenant_docs'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(255), nullable=False)
    doc_name = Column(String(500), nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow)
    num_entries = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint('tenant_id', 'doc_name', name='unique_tenant_doc'),)

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the engine
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tenant_doc(db, tenant_id: str, doc_name: str, num_entries: int):
    new_doc = TenantDoc(tenant_id=tenant_id, doc_name=doc_name, num_entries=num_entries)
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc

def update_tenant_doc_entries(db, tenant_id: str, doc_name: str, num_entries: int):
    doc = db.query(TenantDoc).filter(TenantDoc.tenant_id == tenant_id, TenantDoc.doc_name == doc_name).first()
    if doc:
        doc.num_entries = num_entries
        db.commit()
        db.refresh(doc)
    return doc

def delete_tenant_doc(db, tenant_id: str, doc_name: str):
    doc = db.query(TenantDoc).filter(TenantDoc.tenant_id == tenant_id, TenantDoc.doc_name == doc_name).first()
    if doc:
        db.delete(doc)
        db.commit()
    return doc

def get_tenant_docs(db, tenant_id: str):
    return db.query(TenantDoc).filter(TenantDoc.tenant_id == tenant_id).all()