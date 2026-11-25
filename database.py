import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
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
    tempo_tela        TEXT,
    tempo_tela_min    INTEGER,
    relato_livre      TEXT
);
CREATE TABLE IF NOT EXISTS espaco (            -- anotações livres (/espaco)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em TEXT NOT NULL, data TEXT NOT NULL, texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eventos (           -- linha do tempo
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL, titulo TEXT NOT NULL, descricao TEXT DEFAULT '',
    categoria TEXT NOT NULL DEFAULT 'geral', criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lembretes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL, mensagem TEXT DEFAULT '',
    categoria TEXT NOT NULL DEFAULT 'geral',
    tipo TEXT NOT NULL CHECK (tipo IN ('diario', 'semanal')),
    dias TEXT NOT NULL DEFAULT '',             -- 'mon,wed,fri' (só no semanal)
    horario TEXT NOT NULL,                     -- HH:MM
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lembrete_log (       -- toques em "✅ Fiz"
    lembrete_id INTEGER NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (lembrete_id, data)
);
"""

# Colunas adicionadas depois do MVP: aplicadas automaticamente em bancos já existentes.
COLUNAS_NOVAS = {
    "tempo_sozinho": "TEXT",
    "tempo_sozinho_min": "INTEGER",
    "habitos_ruins": "TEXT",
    "correria": "INTEGER CHECK (correria BETWEEN 1 AND 5)",
    "pressao_social": "INTEGER CHECK (pressao_social BETWEEN 1 AND 5)",
    "estudou_leu": "INTEGER CHECK (estudou_leu IN (0, 1))",
    "hobby_feito": "INTEGER CHECK (hobby_feito IN (0, 1))",
    "energia": "INTEGER CHECK (energia BETWEEN 1 AND 5)",
    "motivacao": "INTEGER CHECK (motivacao BETWEEN 1 AND 5)",
    "ansiedade": "INTEGER CHECK (ansiedade BETWEEN 1 AND 5)",
    "sobrecarga": "INTEGER CHECK (sobrecarga BETWEEN 1 AND 5)",
    "irritabilidade": "INTEGER CHECK (irritabilidade BETWEEN 1 AND 5)",
    "procrastinacao": "INTEGER CHECK (procrastinacao BETWEEN 1 AND 5)",
    "sensacao_controle": "INTEGER CHECK (sensacao_controle BETWEEN 1 AND 5)",
    "raiva": "INTEGER CHECK (raiva BETWEEN 1 AND 5)",
    "medo": "INTEGER CHECK (medo BETWEEN 1 AND 5)",
    "culpa": "INTEGER CHECK (culpa BETWEEN 0 AND 10)",
    "produtividade": "INTEGER CHECK (produtividade BETWEEN 1 AND 5)",
    "satisfacao": "INTEGER CHECK (satisfacao BETWEEN 1 AND 5)",
}
WD = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def agora() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def hoje() -> str:
    return agora().date().isoformat()


def _ts() -> str:
    return agora().isoformat(timespec="seconds")


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
        existentes = {r["name"] for r in conn.execute("PRAGMA table_info(registros)")}
        for col, tipo in COLUNAS_NOVAS.items():
            if col not in existentes:
                conn.execute(f"ALTER TABLE registros ADD COLUMN {col} {tipo}")


# ---------- registros diários ----------
def salvar_resposta(data: str, campo: str, valor):
    if campo not in CAMPOS_VALIDOS:  # whitelist: o nome da coluna nunca vem do usuário
        raise ValueError(f"Campo inválido: {campo}")
    ts = _ts()
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
    return [por_data.get((inicio + timedelta(days=i)).isoformat(),
                         {**vazio, "data": (inicio + timedelta(days=i)).isoformat()})
            for i in range(dias)]


# ---------- espaço (anotações) ----------
def salvar_espaco(texto: str):
    with conectar() as conn:
        conn.execute("INSERT INTO espaco (criado_em, data, texto) VALUES (?, ?, ?)", (_ts(), hoje(), texto))


def listar_espaco(dias: int = 7, limite: int = 50):
    ini = (agora().date() - timedelta(days=dias - 1)).isoformat()
    with conectar() as conn:
        rows = conn.execute("SELECT data, criado_em, texto FROM espaco WHERE data >= ? ORDER BY id DESC LIMIT ?",
                            (ini, limite)).fetchall()
    return [dict(r) for r in rows][::-1]


def ultimas_notas(n: int = 5):
    with conectar() as conn:
        rows = conn.execute("SELECT data, texto FROM espaco ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [dict(r) for r in rows][::-1]


# ---------- linha do tempo ----------
def add_evento(data: str, titulo: str, descricao: str = "", categoria: str = "geral") -> int:
    with conectar() as conn:
        return conn.execute(
            "INSERT INTO eventos (data, titulo, descricao, categoria, criado_em) VALUES (?, ?, ?, ?, ?)",
            (data, titulo, descricao, categoria, _ts())).lastrowid


def listar_eventos(dias: int = 90):
    ini = (agora().date() - timedelta(days=dias - 1)).isoformat()
    with conectar() as conn:
        rows = conn.execute("SELECT * FROM eventos WHERE data >= ? ORDER BY data DESC, id DESC", (ini,)).fetchall()
    return [dict(r) for r in rows]


def del_evento(eid: int):
    with conectar() as conn:
        conn.execute("DELETE FROM eventos WHERE id = ?", (eid,))


# ---------- lembretes ----------
def add_lembrete(titulo, mensagem, categoria, tipo, dias, horario) -> int:
    with conectar() as conn:
        return conn.execute(
            """INSERT INTO lembretes (titulo, mensagem, categoria, tipo, dias, horario, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (titulo, mensagem, categoria, tipo, ",".join(dias) if tipo == "semanal" else "", horario, _ts())).lastrowid


def listar_lembretes(apenas_ativos: bool = False):
    sql = "SELECT * FROM lembretes" + (" WHERE ativo = 1" if apenas_ativos else "") + " ORDER BY horario, id"
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_lembrete(lid: int):
    with conectar() as conn:
        r = conn.execute("SELECT * FROM lembretes WHERE id = ?", (lid,)).fetchone()
    return dict(r) if r else None


def toggle_lembrete(lid: int):
    with conectar() as conn:
        conn.execute("UPDATE lembretes SET ativo = 1 - ativo WHERE id = ?", (lid,))


def del_lembrete(lid: int):
    with conectar() as conn:
        conn.execute("DELETE FROM lembrete_log WHERE lembrete_id = ?", (lid,))
        conn.execute("DELETE FROM lembretes WHERE id = ?", (lid,))


def marcar_lembrete(lid: int, data: str):
    with conectar() as conn:
        conn.execute("INSERT OR IGNORE INTO lembrete_log (lembrete_id, data) VALUES (?, ?)", (lid, data))


def habitos_resumo(dias: int = 30):
    """Constância de cada lembrete ativo: feitos (toques em ✅) / esperados (dias agendados desde a criação)."""
    fim = agora().date()
    ini = fim - timedelta(days=dias - 1)
    datas = [ini + timedelta(days=i) for i in range(dias)]
    out = []
    with conectar() as conn:
        for l in conn.execute("SELECT * FROM lembretes WHERE ativo = 1 ORDER BY horario, id").fetchall():
            criado = date.fromisoformat(l["criado_em"][:10])
            validos = [d for d in datas if d >= criado]
            if l["tipo"] == "semanal":
                sel = set(filter(None, l["dias"].split(",")))
                validos = [d for d in validos if WD[d.weekday()] in sel]
            feitos = conn.execute(
                "SELECT COUNT(*) FROM lembrete_log WHERE lembrete_id = ? AND data BETWEEN ? AND ?",
                (l["id"], ini.isoformat(), fim.isoformat())).fetchone()[0]
            out.append({"id": l["id"], "titulo": l["titulo"], "categoria": l["categoria"],
                        "feitos": feitos, "esperados": len(validos)})
    return out


# ---------- sequência sem um comportamento (ex.: pornografia) ----------
def streak(campo: str = "pornografia"):
    """Dias seguidos sem registro '1' no campo. Conta desde a última recaída (ou do 1º registro)."""
    if campo not in CAMPOS_VALIDOS:
        raise ValueError(campo)
    hoje_d = agora().date()
    with conectar() as conn:
        recaidas = [date.fromisoformat(r[0]) for r in
                    conn.execute(f"SELECT data FROM registros WHERE {campo} = 1 ORDER BY data")]
        prim = conn.execute("SELECT MIN(data) FROM registros").fetchone()[0]
    if not prim:
        return {"atual": 0, "melhor": 0, "recaidas": 0, "ultima_recaida": None}
    prim = date.fromisoformat(prim)
    if recaidas:
        atual = (hoje_d - recaidas[-1]).days
        marcos = [prim - timedelta(days=1)] + recaidas
        melhor = max([(b - a).days - 1 for a, b in zip(marcos, marcos[1:])] + [atual])
    else:
        atual = melhor = (hoje_d - prim).days + 1
    return {"atual": atual, "melhor": melhor, "recaidas": len(recaidas),
            "ultima_recaida": recaidas[-1].isoformat() if recaidas else None}