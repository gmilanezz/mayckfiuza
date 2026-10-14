import os, uuid, base64
from datetime import datetime, timedelta, date
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Text,
    Boolean,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel

BASE = os.path.dirname(__file__)

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DB = DATABASE_URL
else:
    DB = "sqlite:///" + os.path.join(BASE, "mayck.db")

if DB.startswith("postgres://"):
    DB = DB.replace("postgres://", "postgresql+psycopg://", 1)
elif DB.startswith("postgresql://"):
    DB = DB.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DB,
    connect_args={"check_same_thread": False}
    if DB.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
pwd = CryptContext(schemes=["bcrypt"])
oauth = OAuth2PasswordBearer(tokenUrl="/api/login")
SECRET = os.getenv("SECRET_KEY", "change-this-in-production")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    role = Column(String)
    professor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    active = Column(Boolean, default=True)


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    professor_id = Column(Integer, ForeignKey("users.id"))
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    student_name = Column(String, default="")
    weekday = Column(Integer)
    time = Column(String)
    note = Column(String, default="")


class Workout(Base):
    __tablename__ = "workouts"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    professor_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    content = Column(Text)
    periodization = Column(String, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class Completion(Base):
    __tablename__ = "completions"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    workout_id = Column(Integer, ForeignKey("workouts.id"))
    completed_at = Column(DateTime, default=datetime.utcnow)


class Weight(Base):
    __tablename__ = "weights"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    value = Column(Float)
    measured_on = Column(Date, default=date.today)


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)

# Migração idempotente para bancos já existentes.
with engine.begin() as conn:
    if DB.startswith("sqlite"):
        lesson_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(lessons)"))}
    else:
        lesson_columns = {row[0] for row in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'lessons'"
        ))}
    if "student_name" not in lesson_columns:
        conn.execute(text("ALTER TABLE lessons ADD COLUMN student_name VARCHAR DEFAULT ''"))

app = FastAPI(title="Mayck Fiuza Training API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def token(u):
    return jwt.encode(
        {
            "sub": str(u.id),
            "role": u.role,
            "exp": datetime.utcnow() + timedelta(days=3650),
        },
        SECRET,
        algorithm="HS256",
    )


def me(t=Depends(oauth), s: Session = Depends(db)):
    try:
        uid = int(jwt.decode(t, SECRET, algorithms=["HS256"])["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Sessão inválida")
    u = s.get(User, uid)
    if not u or not u.active:
        raise HTTPException(401, "Usuário inválido")
    return u


def allow_prof(u):
    if u.role not in ("professor", "admin"):
        raise HTTPException(403, "Acesso de professor necessário")


class StudentIn(BaseModel):
    name: str
    username: str
    password: str


class RegisterIn(BaseModel):
    name: str
    username: str
    password: str
    role: str
    invite_code: str
    professor_id: Optional[int] = None


class ResetPasswordIn(BaseModel):
    username: str
    invite_code: str
    new_password: str


class LessonIn(BaseModel):
    student_name: str
    weekday: int
    time: str
    note: str = ""


class WorkoutIn(BaseModel):
    student_id: int
    title: str
    content: str
    periodization: str = ""


class WeightIn(BaseModel):
    value: float
    measured_on: date = date.today()


INVITE_CODE = os.getenv("MAYCK_INVITE_CODE", "DG5A1")


@app.get("/api/public/professors")
def public_professors(s: Session = Depends(db)):
    return [
        {"id": x.id, "name": x.name}
        for x in s.query(User)
        .filter(User.role == "professor", User.active == True)
        .order_by(User.name)
        .all()
    ]


@app.post("/api/register")
def register(x: RegisterIn, s: Session = Depends(db)):
    code = x.invite_code.strip().upper()
    if len(code) != 5 or not code.isalnum() or code != INVITE_CODE.upper():
        raise HTTPException(403, "Código de acesso inválido")
    if x.role not in ("professor", "student"):
        raise HTTPException(400, "Tipo de conta inválido")
    username = x.username.strip().lower()
    if len(x.password) < 5:
        raise HTTPException(400, "A senha deve ter pelo menos 5 caracteres")
    if s.query(User).filter(User.username == username).first():
        raise HTTPException(409, "Usuário já existe")
    professor_id = None
    if x.role == "student":
        prof = s.get(User, x.professor_id) if x.professor_id else None
        if not prof or prof.role != "professor":
            raise HTTPException(400, "Selecione um professor válido")
        professor_id = prof.id
    u = User(
        name=x.name.strip(),
        username=username,
        password_hash=pwd.hash(x.password),
        role=x.role,
        professor_id=professor_id,
    )
    s.add(u)
    s.commit()
    s.refresh(u)
    return {
        "access_token": token(u),
        "token_type": "bearer",
        "user": {"id": u.id, "name": u.name, "role": u.role},
    }


@app.post("/api/reset-password")
def reset_password(x: ResetPasswordIn, s: Session = Depends(db)):
    code = x.invite_code.strip().upper()
    if len(code) != 5 or not code.isalnum() or code != INVITE_CODE.upper():
        raise HTTPException(403, "Código de convite inválido")
    if len(x.new_password) < 5:
        raise HTTPException(400, "A nova senha deve ter pelo menos 5 caracteres")
    username = x.username.strip().lower()
    u = s.query(User).filter(User.username == username, User.active == True).first()
    if not u:
        raise HTTPException(404, "Usuário não encontrado")
    u.password_hash = pwd.hash(x.new_password)
    s.commit()
    return {"ok": True, "message": "Senha redefinida com sucesso"}


@app.post("/api/login")
def login(f: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(db)):
    u = s.query(User).filter(User.username == f.username).first()
    if not u or not pwd.verify(f.password, u.password_hash):
        raise HTTPException(401, "Usuário ou senha inválidos")
    return {
        "access_token": token(u),
        "token_type": "bearer",
        "user": {"id": u.id, "name": u.name, "role": u.role},
    }


@app.get("/api/me")
def profile(u=Depends(me)):
    return {"id": u.id, "name": u.name, "username": u.username, "role": u.role}


@app.get("/api/students")
def students(u=Depends(me), s: Session = Depends(db)):
    if u.role == "student":
        return [{"id": u.id, "name": u.name}]
    q = s.query(User).filter(User.role == "student")
    q = q if u.role == "admin" else q.filter(User.professor_id == u.id)
    return [
        {
            "id": x.id,
            "name": x.name,
            "username": x.username,
            "professor_id": x.professor_id,
        }
        for x in q.all()
    ]


@app.post("/api/students")
def add_student(x: StudentIn, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    if len(x.password) < 5:
        raise HTTPException(400, "A senha deve ter pelo menos 5 caracteres")
    if s.query(User).filter(User.username == x.username).first():
        raise HTTPException(409, "Usuário já existe")
    st = User(
        name=x.name,
        username=x.username,
        password_hash=pwd.hash(x.password),
        role="student",
        professor_id=u.id,
    )
    s.add(st)
    s.commit()
    s.refresh(st)
    return {"id": st.id}


@app.delete("/api/students/{sid}")
def del_student(sid: int, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    st = s.get(User, sid)
    if not st or (u.role != "admin" and st.professor_id != u.id):
        raise HTTPException(404)
    s.delete(st)
    s.commit()
    return {"ok": True}


@app.get("/api/lessons")
def lessons(team: bool = False, u=Depends(me), s: Session = Depends(db)):
    q = s.query(Lesson)
    if u.role == "professor" and not team:
        q = q.filter((Lesson.professor_id == u.id) | (Lesson.professor_id.is_(None)))
    elif u.role == "student":
        q = q.filter(Lesson.student_id == u.id)
    users = {x.id: x.name for x in s.query(User).all()}
    return [
        {
            "id": x.id,
            "professor_id": x.professor_id,
            "professor": users.get(x.professor_id),
            "student_id": x.student_id,
            "student": x.student_name or users.get(x.student_id) or "Aluno",
            "weekday": x.weekday,
            "time": x.time,
            "note": x.note,
        }
        for x in q.all()
    ]


@app.post("/api/lessons")
def add_lesson(x: LessonIn, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    student_name = x.student_name.strip()
    if not student_name:
        raise HTTPException(400, "Informe o nome do aluno.")
    a = Lesson(professor_id=u.id, student_id=None, student_name=student_name, weekday=x.weekday, time=x.time, note=x.note)
    s.add(a)
    s.commit()
    return {"id": a.id}


@app.delete("/api/lessons/{lid}")
def del_lesson(lid: int, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    x = s.get(Lesson, lid)
    if not x or (u.role != "admin" and x.professor_id != u.id):
        raise HTTPException(404)
    s.delete(x)
    s.commit()
    return {"ok": True}


@app.get("/api/workouts")
def workouts(u=Depends(me), s: Session = Depends(db)):
    q = s.query(Workout)
    if u.role == "student":
        q = q.filter((Workout.student_id == u.id) | ((Workout.student_id.is_(None)) & (Workout.professor_id.is_(None))))
    elif u.role == "professor":
        q = q.filter((Workout.professor_id == u.id) | ((Workout.student_id.is_(None)) & (Workout.professor_id.is_(None))))
    return [
        {
            "id": x.id,
            "student_id": x.student_id,
            "title": x.title,
            "content": x.content,
            "periodization": x.periodization,
            "updated_at": x.updated_at,
        }
        for x in q.all()
    ]


@app.post("/api/workouts")
def save_workout(x: WorkoutIn, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    st = s.get(User, x.student_id)
    if not st or (u.role != "admin" and st.professor_id != u.id):
        raise HTTPException(403)
    w = Workout(professor_id=u.id, **x.model_dump())
    s.add(w)
    s.commit()
    return {"id": w.id}


@app.get("/api/workouts/{wid}")
def workout_detail(wid: int, u=Depends(me), s: Session = Depends(db)):
    w = s.get(Workout, wid)
    if not w:
        raise HTTPException(404, "Treino não encontrado")
    is_demo = w.student_id is None and w.professor_id is None
    if not is_demo and u.role == "student" and w.student_id != u.id:
        raise HTTPException(403)
    if not is_demo and u.role == "professor" and w.professor_id != u.id:
        raise HTTPException(403)
    return {
        "id": w.id,
        "student_id": w.student_id,
        "title": w.title,
        "content": w.content,
        "periodization": w.periodization,
        "updated_at": w.updated_at,
    }


@app.post("/api/workouts/{wid}/complete")
def complete(wid: int, u=Depends(me), s: Session = Depends(db)):
    if u.role != "student":
        raise HTTPException(403)
    w = s.get(Workout, wid)
    if not w or w.student_id != u.id:
        raise HTTPException(404)
    s.add(Completion(student_id=u.id, workout_id=wid))
    s.commit()
    return {"ok": True}


@app.get("/api/weights/{sid}")
def weights(sid: int, u=Depends(me), s: Session = Depends(db)):
    if u.role == "student" and sid != u.id:
        raise HTTPException(403)
    if u.role == "professor":
        st = s.get(User, sid)
        if not st or st.professor_id != u.id:
            raise HTTPException(403)
    return [
        {"value": x.value, "measured_on": x.measured_on}
        for x in s.query(Weight)
        .filter(Weight.student_id == sid)
        .order_by(Weight.measured_on)
        .all()
    ]


@app.post("/api/weights")
def add_weight(x: WeightIn, u=Depends(me), s: Session = Depends(db)):
    if u.role != "student":
        raise HTTPException(403)
    s.add(Weight(student_id=u.id, **x.model_dump()))
    s.commit()
    return {"ok": True}


@app.post("/api/photos")
async def photos(
    files: List[UploadFile] = File(...), u=Depends(me), s: Session = Depends(db)
):
    if u.role != "student":
        raise HTTPException(403)
    if not files:
        raise HTTPException(400, "Selecione ao menos uma foto")
    saved = []
    allowed = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    max_bytes = 4 * 1024 * 1024
    for file in files:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in allowed:
            raise HTTPException(400, f"Formato inválido: {file.filename}")
        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(400, f"A foto {file.filename} excede o limite de 4 MB")
        mime = allowed[ext]
        path = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
        s.add(Photo(student_id=u.id, path=path))
        saved.append({"filename": file.filename, "stored": True})
    s.commit()
    return {"files": saved, "count": len(saved)}


@app.get("/api/photos/{sid}")
def student_photos(sid: int, u=Depends(me), s: Session = Depends(db)):
    st = s.get(User, sid)
    if not st or st.role != "student":
        raise HTTPException(404, "Aluno não encontrado")
    if u.role == "student" and sid != u.id:
        raise HTTPException(403)
    if u.role == "professor" and st.professor_id != u.id:
        raise HTTPException(403)
    rows = (
        s.query(Photo)
        .filter(Photo.student_id == sid)
        .order_by(Photo.created_at.desc())
        .all()
    )
    return [{"id": x.id, "path": x.path, "created_at": x.created_at} for x in rows]

