import os, uuid, base64, calendar, secrets, urllib.request, json
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
    scheduled_date = Column(Date, nullable=True, index=True)
    time = Column(String)
    note = Column(String, default="")
    status = Column(String, default="pending", nullable=False)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)


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


class PaymentPlan(Base):
    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    professor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    cycle = Column(String, nullable=False)
    amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("payment_plans.id"), nullable=False)
    due_date = Column(Date, nullable=False)
    paid = Column(Boolean, default=False, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    notified_at = Column(DateTime, nullable=True)


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
    for column, definition in (("status", "VARCHAR DEFAULT 'pending' NOT NULL"),
                               ("completed_at", "TIMESTAMP"), ("cancelled_at", "TIMESTAMP"),
                               ("scheduled_date", "DATE")):
        if column not in lesson_columns:
            conn.execute(text(f"ALTER TABLE lessons ADD COLUMN {column} {definition}"))

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
    student_id: Optional[int] = None
    student_name: str
    scheduled_date: date
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


INVITE_CODE = os.getenv("MAYCK_INVITE_CODE", "M3Y8K")


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
    if x.role != "student":
        raise HTTPException(400, "Tipo de conta inválido")
    username = x.username.strip().lower()
    if len(x.password) < 5:
        raise HTTPException(400, "A senha deve ter pelo menos 5 caracteres")
    if s.query(User).filter(User.username == username).first():
        raise HTTPException(409, "Usuário já existe")
    professor_id = None
    if x.role == "student":
        prof = s.query(User).filter(User.role == "professor", User.active == True).first()
        if not prof or prof.role != "professor":
            raise HTTPException(400, "Professor ainda não configurado")
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
    if u.role != "student":
        raise HTTPException(403, "Recuperação do professor indisponível por código de aluno")
    u.password_hash = pwd.hash(x.new_password)
    s.commit()
    return {"ok": True, "message": "Senha redefinida com sucesso"}


@app.post("/api/login")
def login(f: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(db)):
    u = s.query(User).filter(User.username == f.username).first()
    if not u or not u.active or not pwd.verify(f.password, u.password_hash):
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


def lesson_json(x):
    return {"id": x.id, "professor_id": x.professor_id, "student_id": x.student_id,
            "student": x.student_name, "weekday": x.weekday,
            "scheduled_date": x.scheduled_date.isoformat() if x.scheduled_date else None, "time": x.time,
            "note": x.note, "status": x.status or "pending",
            "completed_at": x.completed_at.isoformat() if x.completed_at else None,
            "cancelled_at": x.cancelled_at.isoformat() if x.cancelled_at else None}


@app.get("/api/lessons")
def lessons(team: bool = False, u=Depends(me), s: Session = Depends(db)):
    q = s.query(Lesson)
    if u.role == "professor":
        q = q.filter(Lesson.professor_id == u.id)
    elif u.role == "student":
        q = q.filter(Lesson.student_id == u.id)
    return [lesson_json(x) for x in q.order_by(Lesson.scheduled_date, Lesson.time).all()]


@app.get("/api/students/{sid}/lessons")
def student_lessons(sid: int, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    student = s.get(User, sid)
    if not student or student.role != "student" or student.professor_id != u.id:
        raise HTTPException(404, "Aluno não encontrado")
    return [lesson_json(x) for x in s.query(Lesson).filter(
        Lesson.student_id == sid, Lesson.professor_id == u.id
    ).order_by(Lesson.scheduled_date, Lesson.time).all()]


@app.get("/api/lessons/monthly-summary")
def lesson_summary(month: Optional[str] = None, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    try:
        selected = date.fromisoformat((month or date.today().strftime("%Y-%m")) + "-01")
    except ValueError:
        raise HTTPException(400, "Mês inválido: use AAAA-MM")
    first = datetime(selected.year, selected.month, 1)
    last = datetime(selected.year + (selected.month == 12), (selected.month % 12) + 1, 1)
    rows = s.query(Lesson).filter(Lesson.professor_id == u.id).all()
    # Os agendamentos são semanais sem data de início; o resumo contabiliza
    # os eventos concluídos/cancelados no mês, e os pendentes atuais.
    completed = sum(x.status == "completed" and x.completed_at and first <= x.completed_at < last for x in rows)
    cancelled = sum(x.status == "cancelled" and x.cancelled_at and first <= x.cancelled_at < last for x in rows)
    pending = sum((x.status or "pending") == "pending" for x in rows) if selected.year == date.today().year and selected.month == date.today().month else 0
    return {"month": selected.strftime("%Y-%m"), "total": completed + cancelled + pending,
            "completed": completed, "cancelled": cancelled, "pending": pending}


@app.post("/api/lessons")
def add_lesson(x: LessonIn, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    student_name = x.student_name.strip()
    student_id = x.student_id
    if student_id is not None:
        student = s.get(User, student_id)
        if not student or student.role != "student" or student.professor_id != u.id:
            raise HTTPException(400, "Aluno não pertence ao professor")
        student_name = student.name
    elif student_name:
        matches = s.query(User).filter(User.professor_id == u.id, User.role == "student").all()
        matches = [st for st in matches if st.name.casefold() == student_name.casefold()]
        if len(matches) == 1:
            student_id = matches[0].id
        elif len(matches) > 1:
            raise HTTPException(400, "Nome repetido; selecione o aluno cadastrado")
    if not student_name:
        raise HTTPException(400, "Informe o nome do aluno")
    a = Lesson(professor_id=u.id, student_id=student_id, student_name=student_name,
               scheduled_date=x.scheduled_date, weekday=x.scheduled_date.weekday(),
               time=x.time, note=x.note, status="pending")
    s.add(a)
    s.commit()
    return {"id": a.id}


@app.patch("/api/lessons/{lid}/status")
def update_lesson_status(lid: int, status: str, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    if status not in ("completed", "cancelled"):
        raise HTTPException(400, "Status inválido")
    lesson = s.get(Lesson, lid)
    if not lesson or lesson.professor_id != u.id:
        raise HTTPException(404, "Aula não encontrada")
    if (lesson.status or "pending") != "pending":
        raise HTTPException(409, "Aula já finalizada")
    if status == "completed" and lesson.student_id is None:
        raise HTTPException(400, "Associe a aula a um aluno cadastrado antes de concluir")
    lesson.status = status
    if status == "completed":
        lesson.completed_at = datetime.utcnow()
    else:
        lesson.cancelled_at = datetime.utcnow()
    s.commit()
    return lesson_json(lesson)


@app.delete("/api/lessons/{lid}")
def del_lesson(lid: int, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    lesson = s.get(Lesson, lid)
    if not lesson or lesson.professor_id != u.id:
        raise HTTPException(404)
    if (lesson.status or "pending") != "pending":
        raise HTTPException(409, "Aula já finalizada")
    lesson.status = "cancelled"
    lesson.cancelled_at = datetime.utcnow()
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



# Conta única do professor: criada apenas por operação administrativa com segredo privado.
# Configure MAYCK_ADMIN_USERNAME, MAYCK_ADMIN_PASSWORD e MAYCK_ADMIN_NAME no ambiente.
def ensure_teacher():
    username = os.getenv("MAYCK_ADMIN_USERNAME", "mayck").strip().lower()
    password = os.getenv("MAYCK_ADMIN_PASSWORD", "")
    if not password:
        # Local SQLite: allow initial setup using the explicit helper script.
        # Production/Neon: require MAYCK_ADMIN_PASSWORD in the environment.
        return
    if len(password) < 6:
        raise RuntimeError("MAYCK_ADMIN_PASSWORD deve ter pelo menos 6 caracteres")
    with SessionLocal() as session:
        teacher = session.query(User).filter(User.role == "professor").order_by(User.id).first()
        if teacher is None:
            if session.query(User).filter(User.username == username).first():
                raise RuntimeError("Nome de usuário do professor já está em uso")
            session.add(User(name=os.getenv("MAYCK_ADMIN_NAME", "Mayck Fiuza"), username=username, password_hash=pwd.hash(password), role="professor", active=True))
            session.commit()

ensure_teacher()

CYCLES = {"mensal": 1, "trimestral": 3, "semestral": 6, "anual": 12}

def add_months(day, count):
    month = day.month - 1 + count
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))

class PaymentPlanIn(BaseModel):
    student_id: int
    start_date: date
    cycle: str
    amount: Optional[float] = None

class PaymentUpdate(BaseModel):
    paid: bool

@app.get("/api/payments")
def get_payments(u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    today = date.today()
    result = []
    students = s.query(User).filter(User.role == "student", User.professor_id == u.id).order_by(User.name).all()
    for student in students:
        plan = s.query(PaymentPlan).filter_by(student_id=student.id, professor_id=u.id).first()
        payments = []
        if plan:
            # Gerar vencimentos até 12 meses à frente, mantendo o dia-base original.
            end = add_months(today, 12)
            n = 0
            while n < 600:
                due = add_months(plan.start_date, n * CYCLES[plan.cycle])
                if due > end: break
                if due >= plan.start_date:
                    existing = s.query(Payment).filter_by(plan_id=plan.id, due_date=due).first()
                    if not existing:
                        existing = Payment(plan_id=plan.id, due_date=due, paid=False)
                        s.add(existing)
                n += 1
            s.commit()
            for payment in s.query(Payment).filter_by(plan_id=plan.id).order_by(Payment.due_date).all():
                payments.append({"id": payment.id, "due_date": payment.due_date.isoformat(), "paid": payment.paid, "overdue": not payment.paid and payment.due_date < today, "alert": not payment.paid and payment.due_date <= today - timedelta(days=1)})
        result.append({"student_id": student.id, "student_name": student.name, "cycle": plan.cycle if plan else None, "start_date": plan.start_date.isoformat() if plan else None, "amount": plan.amount if plan else None, "payments": payments})
    return result

@app.put("/api/payments/plan")
def put_payment_plan(x: PaymentPlanIn, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    student = s.get(User, x.student_id)
    if not student or student.role != "student" or student.professor_id != u.id:
        raise HTTPException(404, "Aluno não encontrado")
    if x.cycle not in CYCLES: raise HTTPException(400, "Periodicidade inválida")
    if x.amount is not None and x.amount < 0: raise HTTPException(400, "Valor inválido")
    plan = s.query(PaymentPlan).filter_by(student_id=student.id).first()
    if plan:
        # Não apagar registros quitados; exigir confirmação administrativa para mudar um plano com pagamentos.
        if s.query(Payment).filter_by(plan_id=plan.id, paid=True).first():
            raise HTTPException(409, "Há pagamentos quitados neste plano; não é possível alterar a recorrência sem preservar o histórico")
        s.query(Payment).filter_by(plan_id=plan.id).delete()
        plan.start_date, plan.cycle, plan.amount = x.start_date, x.cycle, x.amount
    else:
        s.add(PaymentPlan(student_id=student.id, professor_id=u.id, start_date=x.start_date, cycle=x.cycle, amount=x.amount))
    s.commit()
    return {"ok": True}

@app.patch("/api/payments/{payment_id}")
def set_payment(payment_id: int, x: PaymentUpdate, u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    payment = s.get(Payment, payment_id)
    plan = s.get(PaymentPlan, payment.plan_id) if payment else None
    if not plan or plan.professor_id != u.id: raise HTTPException(404, "Pagamento não encontrado")
    payment.paid = x.paid
    payment.paid_at = datetime.utcnow() if x.paid else None
    s.commit()
    return {"ok": True}

@app.get("/api/payments/alerts")
def payment_alerts(u=Depends(me), s: Session = Depends(db)):
    allow_prof(u)
    today = date.today()
    rows = s.query(Payment, PaymentPlan, User).join(PaymentPlan, Payment.plan_id == PaymentPlan.id).join(User, PaymentPlan.student_id == User.id).filter(PaymentPlan.professor_id == u.id, Payment.paid == False, Payment.due_date < today).order_by(Payment.due_date).all()
    return [{"student_name": student.name, "due_date": payment.due_date.isoformat(), "days_late": (today - payment.due_date).days} for payment, plan, student in rows]

# Notificação externa opcional: Vercel Cron chama este endpoint diariamente.
# Requer CRON_SECRET, RESEND_API_KEY, MAYCK_ALERT_EMAIL e RESEND_FROM_EMAIL.
@app.get("/api/cron/payment-alerts")
def cron_payment_alerts(authorization: Optional[str] = __import__('fastapi').Header(default=None), s: Session = Depends(db)):
    secret = os.getenv("CRON_SECRET")
    if not secret or not secrets.compare_digest(authorization or "", "Bearer " + secret):
        raise HTTPException(401, "Não autorizado")
    key = os.getenv("RESEND_API_KEY")
    target = os.getenv("MAYCK_ALERT_EMAIL")
    sender = os.getenv("RESEND_FROM_EMAIL")
    if not (key and target and sender):
        return {"sent": 0, "configured": False}
    today = date.today()
    rows = s.query(Payment, PaymentPlan, User).join(PaymentPlan, Payment.plan_id == PaymentPlan.id).join(User, PaymentPlan.student_id == User.id).filter(Payment.paid == False, Payment.due_date < today, Payment.notified_at.is_(None)).all()
    sent = 0
    for payment, plan, student in rows:
        payload = json.dumps({"from": sender, "to": [target], "subject": "Mayck Fiuza — pagamento atrasado", "text": f"Aluno: {student.name}\nVencimento: {payment.due_date:%d/%m/%Y}\nAtraso: {(today-payment.due_date).days} dia(s).\nPagamento pendente."}).encode()
        request = urllib.request.Request("https://api.resend.com/emails", data=payload, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300: continue
            payment.notified_at = datetime.utcnow()
            s.commit()
            sent += 1
        except Exception:
            s.rollback()
    return {"sent": sent, "configured": True}
