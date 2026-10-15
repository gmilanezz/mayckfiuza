"""Apaga SOMENTE dados das tabelas do aplicativo, preservando a estrutura.
Requer DATABASE_URL e confirmação explícita. Execute localmente, NUNCA no deploy.
"""
import os
from sqlalchemy import create_engine, text

url = os.getenv('DATABASE_URL')
if not url or 'postgres' not in url:
    raise SystemExit('Configure DATABASE_URL do banco Neon desejado. SQLite não é permitido.')
url = url.replace('postgres://','postgresql+psycopg://',1).replace('postgresql://','postgresql+psycopg://',1)
engine = create_engine(url)
with engine.connect() as conn:
    dbname = conn.execute(text('SELECT current_database()')).scalar()
    host = engine.url.host
print(f'ATENÇÃO: exclusão IRREVERSÍVEL de todos os dados do aplicativo em {dbname} / {host}.')
print('Tabelas: payments, payment_plans, photos, weights, completions, workouts, lessons, users')
confirm = input('Digite exatamente ZERAR MAYCK para continuar: ')
if confirm != 'ZERAR MAYCK':
    raise SystemExit('Operação cancelada.')
with engine.begin() as conn:
    conn.execute(text('TRUNCATE TABLE payments, payment_plans, photos, weights, completions, workouts, lessons, users RESTART IDENTITY CASCADE'))
print('Dados apagados. As tabelas foram preservadas. Reinicie a API para recriar o professor com MAYCK_ADMIN_PASSWORD.')
