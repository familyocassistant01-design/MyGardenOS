from hashlib import sha256
from random import randint
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from app.database import Base, SessionLocal, engine, get_db
from app.models.entities import Device, Family, FamilyMember, HelpArticle, Notification, Setting, User
from app.schemas.dto import (
    AboutOut, BindDeviceIn, DeviceOut, FamilyCreate, FamilyOut, FamilyUpdate,
    HelpArticleOut, NotificationOut, ProfileUpdate, SettingsOut, SettingsUpdate, UserOut,
)

app = FastAPI(title="MyGardenOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HELP_TITLES = [
    "Operation instructions", "Installation instructions", "Mapping instructions",
    "Quick Start instructions", "Install blade disc", "Replace the battery",
    "Install the garage", "Clean the mower",
]

def current_user(db: Session) -> User:
    user = db.query(User).filter(User.email == "demo@example.com").first()
    if not user:
        user = User(email="demo@example.com", username="Hector", gender="Male")
        db.add(user); db.flush()
        fam = Family(code="F612I5L1", name="happy family", creator_id=user.id)
        db.add(fam); db.flush()
        db.add(FamilyMember(family_id=fam.id, user_id=user.id, role="Family Creator"))
        db.add(Setting(user_id=user.id))
    return user

def seed(db: Session):
    user = current_user(db)
    if db.query(Device).count() == 0:
        db.add_all([
            Device(serial="MOCK-AN1600-001", name="MyGardenOS Mower", model="AN-1600"),
            Device(serial="MOCK-AN1600-002", name="Garden Mower Demo", model="AN-1600"),
        ])
    if db.query(HelpArticle).count() == 0:
        for title in HELP_TITLES:
            slug = title.lower().replace(" ", "-")
            db.add(HelpArticle(slug=slug, title=title, content=f"# {title}\n\nMowers User Manual\n\nThis development-test document is a PDF-like placeholder for {title}.\n\n1. Safety alerts\n2. Specifications\n3. App operation\n4. Maintenance and storage"))
    db.commit()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok", "service": "MyGardenOS API"}

@app.get("/auth/dev-user", response_model=UserOut)
def dev_user(db: Session = Depends(get_db)):
    return current_user(db)

@app.get("/profile", response_model=UserOut)
def get_profile(db: Session = Depends(get_db)):
    return current_user(db)

@app.patch("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    user = current_user(db)
    for field in ["username", "gender", "address"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    if payload.password:
        user.password_hash = sha256(payload.password.encode()).hexdigest()
    db.commit(); db.refresh(user)
    return user

@app.get("/families", response_model=list[FamilyOut])
def list_families(db: Session = Depends(get_db)):
    user = current_user(db)
    return db.query(Family).options(joinedload(Family.members).joinedload(FamilyMember.user)).join(FamilyMember).filter(FamilyMember.user_id == user.id).all()

@app.post("/families", response_model=FamilyOut)
def create_family(payload: FamilyCreate, db: Session = Depends(get_db)):
    user = current_user(db)
    fam = Family(code=f"F{randint(1000000, 9999999)}", name=payload.name, address=payload.address, creator_id=user.id)
    db.add(fam); db.flush(); db.add(FamilyMember(family_id=fam.id, user_id=user.id, role="Family Creator")); db.commit(); db.refresh(fam)
    return db.query(Family).options(joinedload(Family.members).joinedload(FamilyMember.user)).get(fam.id)

@app.patch("/families/{family_id}", response_model=FamilyOut)
def update_family(family_id: int, payload: FamilyUpdate, db: Session = Depends(get_db)):
    fam = db.get(Family, family_id)
    if not fam: raise HTTPException(404, "Family not found")
    if payload.name is not None: fam.name = payload.name
    if payload.address is not None: fam.address = payload.address
    db.commit()
    return db.query(Family).options(joinedload(Family.members).joinedload(FamilyMember.user)).get(family_id)

@app.delete("/families/{family_id}")
def dissolve_family(family_id: int, db: Session = Depends(get_db)):
    fam = db.get(Family, family_id)
    if not fam: raise HTTPException(404, "Family not found")
    db.delete(fam); db.commit()
    return {"status": "dissolved"}

@app.get("/devices", response_model=list[DeviceOut])
def devices(db: Session = Depends(get_db)):
    user = current_user(db)
    return db.query(Device).filter(Device.owner_id == user.id).all()

@app.get("/devices/search", response_model=list[DeviceOut])
def search_devices(db: Session = Depends(get_db)):
    return db.query(Device).filter(Device.owner_id.is_(None)).all()

@app.post("/devices/bind", response_model=DeviceOut)
def bind_device(payload: BindDeviceIn, db: Session = Depends(get_db)):
    user = current_user(db)
    device = db.query(Device).filter(Device.serial == payload.serial).first()
    if not device: raise HTTPException(404, "Device not found")
    device.owner_id = user.id; device.family_id = payload.family_id; device.status = "bound"
    db.commit(); db.refresh(device)
    return device

@app.get("/notifications", response_model=list[NotificationOut])
def notifications(kind: str = Query("device"), read: bool | None = Query(None), db: Session = Depends(get_db)):
    user = current_user(db)
    q = db.query(Notification).filter(Notification.user_id == user.id, Notification.kind == kind)
    if read is not None: q = q.filter(Notification.is_read == read)
    return q.order_by(Notification.created_at.desc()).all()

@app.get("/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    user = current_user(db)
    settings = db.query(Setting).filter(Setting.user_id == user.id).first() or Setting(user_id=user.id)
    db.add(settings); db.commit(); db.refresh(settings)
    return settings

@app.patch("/settings", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    user = current_user(db)
    settings = db.query(Setting).filter(Setting.user_id == user.id).first() or Setting(user_id=user.id)
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(settings, field, value)
    db.add(settings); db.commit(); db.refresh(settings)
    return settings

@app.get("/help/articles", response_model=list[HelpArticleOut])
def help_articles(db: Session = Depends(get_db)):
    return db.query(HelpArticle).order_by(HelpArticle.id).all()

@app.get("/help/articles/{slug}", response_model=HelpArticleOut)
def help_article(slug: str, db: Session = Depends(get_db)):
    article = db.query(HelpArticle).filter(HelpArticle.slug == slug).first()
    if not article: raise HTTPException(404, "Article not found")
    return article

@app.get("/about", response_model=AboutOut)
def about():
    return AboutOut(product="MyGardenOS", version="V0.1.0-dev", update_status="Development build is up to date", privacy_policy="Privacy Policy placeholder for MyGardenOS.", user_agreement="User Agreement placeholder for MyGardenOS.")
