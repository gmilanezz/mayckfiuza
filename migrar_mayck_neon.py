"""Migra APENAS o professor local para Neon após backup e confirmação explícita.
Uso: python migrar_mayck_neon.py --check | --execute
Requer: sqlalchemy, psycopg[binary]. Não executar no deploy.
"""
import argparse, datetime, json, os, sqlite3, sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / 'backend' / 'mayck.db'
TABLES = ['payments','payment_plans','completions','photos','weights','workouts','lessons','users']

def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true')
    group.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not LOCAL.is_file(): sys.exit('ERRO: backend/mayck.db não encontrado')
    local=sqlite3.connect(f'file:{LOCAL}?mode=ro',uri=True)
    local.row_factory=sqlite3.Row
    rows=local.execute("SELECT username,name,role,password_hash,active FROM users WHERE username=? AND role='professor'",('mayck',)).fetchall()
    if len(rows)!=1: sys.exit(f'ERRO: esperado um professor mayck local, encontrado {len(rows)}')
    user=dict(rows[0]); local.close()
    # SQLite armazena booleanos como 0/1; PostgreSQL exige bool nativo.
    user['active'] = bool(user['active'])
    if not user['active'] or not user['password_hash'].startswith(('$2a$','$2b$','$2y$')) or len(user['password_hash'])!=60:
        sys.exit('ERRO: conta local inativa ou hash bcrypt inválido')
    url=os.getenv('NEON_MIGRATION_DATABASE_URL','').strip()
    if not url or 'localhost' in url or '127.0.0.1' in url or not url.startswith(('postgres://','postgresql://','postgresql+psycopg://')):
        sys.exit('ERRO: configure NEON_MIGRATION_DATABASE_URL com a conexão PostgreSQL remota do Neon (não SQLite).')
    if url.startswith('postgres://'): url='postgresql+psycopg://'+url[len('postgres://'):]
    elif url.startswith('postgresql://'): url='postgresql+psycopg://'+url[len('postgresql://'):]
    engine=create_engine(url,connect_args={'connect_timeout':10})
    with engine.connect() as con:
        names=set(inspect(con).get_table_names())
        missing=set(TABLES)-names
        if missing: sys.exit(f'ERRO: tabelas ausentes no Neon: {sorted(missing)}. Faça deploy/inicialize o schema primeiro.')
        expected={'username','name','role','password_hash','active'}
        cols={c['name'] for c in inspect(con).get_columns('users')}
        if not expected<=cols: sys.exit('ERRO: estrutura users incompatível')
        counts={table:con.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one() for table in TABLES}
        print('Registros atuais no Neon:',counts)
        print('Professor local identificado:',user['username'],user['name'],user['role'],'(hash bcrypt presente)')
        if args.check:
            print('VERIFICAÇÃO concluída. Nada foi alterado. Execute --execute apenas se quiser APAGAR os dados de produção.')
            return
        # Backup em arquivo privado, ANTES de qualquer exclusão. Serializa tipos datetime em string.
        backup={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tables':{}}
        for table in TABLES:
            result=con.execute(text(f'SELECT * FROM "{table}"'))
            backup['tables'][table]=[dict(r) for r in result.mappings()]
    folder=ROOT/'backups_neon';folder.mkdir(exist_ok=True)
    filename=folder/('neon_antes_migracao_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
    with filename.open('x',encoding='utf-8') as f: json.dump(backup,f,ensure_ascii=False,indent=2,default=str)
    try: os.chmod(filename,0o600)
    except OSError: pass
    print('BACKUP SALVO EM:',filename)
    print('ATENÇÃO: o backup contém dados pessoais e hashes de senha. Não envie ao GitHub.')
    answer=input('Para apagar TODOS os registros das oito tabelas do NEON e importar apenas mayck, digite exatamente APAGAR NEON E IMPORTAR MAYCK: ')
    if answer!='APAGAR NEON E IMPORTAR MAYCK': sys.exit('Cancelado: Neon não foi alterado.')
    with engine.begin() as con:
        # Exclusão ordenada para preservar a estrutura e respeitar chaves estrangeiras.
        for table in TABLES: con.execute(text(f'DELETE FROM "{table}"'))
        con.execute(text('INSERT INTO users (username,name,role,password_hash,active,professor_id) VALUES (:username,:name,:role,:password_hash,:active,NULL)'),user)
        # Reseta sequence para evitar colisão no próximo cadastro.
        con.execute(text("SELECT setval(pg_get_serial_sequence('users','id'), COALESCE((SELECT MAX(id) FROM users), 1), (SELECT COUNT(*) > 0 FROM users))"))
        n=con.execute(text("SELECT count(*) FROM users WHERE username='mayck' AND role='professor' AND active=true")).scalar_one()
        if n!=1: raise RuntimeError('Falha na validação da conta Mayck; transação revertida')
    print('SUCESSO: Neon limpo e professor mayck importado. Dados anteriores preservados no backup local.')
    print('Teste o login no aplicativo. A senha é a MESMA do SQLite local.')
if __name__=='__main__': main()
