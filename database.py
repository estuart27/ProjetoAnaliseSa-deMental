import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
from questions import CAMPOS_VALIDOS

# Uma linha por DIA. Cada bloco (manhã/tarde/noite) preenche suas colunas na mesma linha;
# o que não foi respondido fica NULL (isso também é um dado: dia sem registro).
SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL UNIQUE,              -- YYYY-MM-DD
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sono_qualidade    INTEGER CHECK (sono_qualidade    BETWEEN 1 AND 5),
    leitura_biblia    INTEGER CHECK (leitura_biblia    IN (0, 1)),
    oracao_manha      INTEGER CHECK (oracao_manha      IN (0, 1)),
    estresse_tarde    INTEGER CHECK (estresse_tarde    BETWEEN 1 AND 5),
    imprevisto        TEXT,
    tristeza_desanimo INTEGER CHECK (tristeza_desanimo BETWEEN 1 AND 5),
    solidao           INTEGER CHECK (solidao           BETWEEN 1 AND 5),
    alimentacao       INTEGER CHECK (alimentacao       BETWEEN 1 AND 5),
    exercicio_fisico  INTEGER CHECK (exercicio_fisico  IN (0, 1)),
    descanso_dia      INTEGER CHECK (descanso_dia      IN (0, 1)),
    pornografia       INTEGER CHECK (pornografia       IN (0, 1)),
    tempo_tela        TEXT,                 -- texto como digitado
    tempo_tela_min    INTEGER,              -- convertido p/ minutos (gráficos)
    relato_livre      TEXT
);
"""


def agora() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def hoje() -> str:
    return agora().date().isoformat()


@contextmanager
def conectar():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with conectar() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def salvar_resposta(data: str, campo: str, valor):
    if campo not in CAMPOS_VALIDOS:  # whitelist: o nome da coluna nunca vem do usuário
        raise ValueError(f"Campo inválido: {campo}")
    ts = agora().isoformat(timespec="seconds")
    with conectar() as conn:
        conn.execute(
            f"""INSERT INTO registros (data, created_at, updated_at, {campo})
                VALUES (?, ?, ?, ?)
                ON CONFLICT(data) DO UPDATE SET {campo} = excluded.{campo},
                                                updated_at = excluded.updated_at""",
            (data, ts, ts, valor),
        )


def get_dia(data: str):
    with conectar() as conn:
        row = conn.execute("SELECT * FROM registros WHERE data = ?", (data,)).fetchone()
    return dict(row) if row else None


def get_serie(dias: int = 14):
    """Últimos N dias em ordem cronológica, incluindo dias sem registro (campos None)."""
    fim = agora().date()
    inicio = fim - timedelta(days=dias - 1)
    with conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM registros WHERE data BETWEEN ? AND ? ORDER BY data",
            (inicio.isoformat(), fim.isoformat()),
        ).fetchall()
    por_data = {r["data"]: dict(r) for r in rows}
    vazio = {c: None for c in CAMPOS_VALIDOS}
    serie = []
    for i in range(dias):
        d = (inicio + timedelta(days=i)).isoformat()
        serie.append(por_data.get(d, {**vazio, "data": d}))
    return serie
