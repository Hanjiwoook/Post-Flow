"""
이미 있는 DB에 새로 생긴 칸을 추가한다.

Base.metadata.create_all()은 없는 표만 만들고, 이미 있는 표에 칸을 추가해 주지 않는다.
그래서 모델에 칸을 추가하면 기존 postflow.db에서 'no such column' 에러가 난다 (6-4에서 posts에 칸 추가, 11/19).
여기서는 모델에는 있고 DB에는 없는 칸만 ALTER TABLE ... ADD COLUMN으로 추가한다.
기존 줄은 새 칸이 비어 있는(NULL) 채로 남는다. 칸을 지우거나 바꾸는 일은 하지 않는다.
"""
from sqlalchemy import inspect, text


def add_missing_columns(engine, metadata) -> list:
    """추가한 칸 목록("표.칸")을 돌려준다."""
    added = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # 표 자체가 없으면 create_all이 만든다
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
                added.append(f"{table.name}.{column.name}")
    return added
