from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    conn.execute(text('TRUNCATE TABLE itens_fiscais, icms_c190, documentos_fiscais RESTART IDENTITY CASCADE'))
    conn.commit()
    print('Truncate concluido.')

    for table in ['itens_fiscais', 'icms_c190', 'documentos_fiscais']:
        count = conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
        size = conn.execute(text(
            f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))"
        )).scalar()
        print(f'{table}: {count} registros | {size}')

    total = conn.execute(text(
        'SELECT pg_size_pretty(pg_database_size(current_database()))'
    )).scalar()
    print(f'Total do banco: {total}')
