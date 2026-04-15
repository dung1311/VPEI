from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import get_settings
from models.container import Container

engine = create_engine(get_settings().database_url)
Session = sessionmaker(bind=engine)
db = Session()
c = db.query(Container).filter_by(license_plate="61C-10750").first()
print("ID:", c.id)
print("Plate:", c.license_plate)
print("is_refrig:", c.is_refrigerated)
print("hasattr:", hasattr(c, 'is_refrigerated'))
