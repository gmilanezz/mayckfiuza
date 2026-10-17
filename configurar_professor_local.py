"""Create or reset the local Mayck professor account (SQLite only).
Run from project root: python configurar_professor_local.py
Does not access Neon and does not alter students.
"""
import getpass
import os
import sqlite3
from pathlib import Path
from passlib.context import CryptContext

ROOT = Path(__file__).resolve().parent
DB = ROOT / "backend" / "mayck.db"
if not DB.is_file():
    raise SystemExit(f"Banco local não encontrado: {DB}. Inicie o backend local primeiro.")
if os.getenv("DATABASE_URL"):
    print("Aviso: DATABASE_URL está configurada, mas este script altera SOMENTE o SQLite local.")
password = getpass.getpass("Nova senha local do Mayck (mínimo 6 caracteres): ")
if len(password) < 6:
    raise SystemExit("A senha precisa ter pelo menos 6 caracteres.")
confirm = getpass.getpass("Repita a senha: ")
if password != confirm:
    raise SystemExit("As senhas não conferem.")
hash_value = CryptContext(schemes=["bcrypt"]).hash(password)
with sqlite3.connect(DB) as conn:
    exists = conn.execute("SELECT id FROM users WHERE username = ?", ("mayck",)).fetchone()
    if exists:
        conn.execute("UPDATE users SET name=?, password_hash=?, role=?, active=1 WHERE id=?", ("Mayck Fiuza", hash_value, "professor", exists[0]))
        print("Conta local 'mayck' atualizada.")
    else:
        teacher = conn.execute("SELECT id, username FROM users WHERE role='professor' LIMIT 1").fetchone()
        if teacher:
            raise SystemExit(f"Já existe outro professor ({teacher[1]}). Nenhum registro alterado.")
        conn.execute("INSERT INTO users (username, password_hash, name, role, active) VALUES (?, ?, ?, ?, 1)", ("mayck", hash_value, "Mayck Fiuza", "professor"))
        print("Conta local 'mayck' criada.")
print("Reinicie o backend e entre com usuário 'mayck' e a senha escolhida.")
