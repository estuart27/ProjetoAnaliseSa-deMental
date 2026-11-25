"""Definição dos blocos de perguntas. Para mudar/adicionar perguntas, mexa só aqui
(e adicione a coluna correspondente em database.py -> COLUNAS_NOVAS)."""
import re

SIM_NAO = [("✅ Sim", 1), ("❌ Não", 0)]
NAO_SIM = [("✅ Não", 0), ("⚠️ Sim", 1)]

BLOCOS = {
    "manha": {
        "titulo": "☀️ Check-in da manhã",
        "perguntas": [
            {"campo": "sono_qualidade", "tipo": "escala",
             "texto": "Como foi a qualidade do seu sono?",
             "legenda": "1 = Péssimo · 5 = Excelente"},
            {"campo": "energia", "tipo": "escala",
             "texto": "Como está sua energia agora?",
             "legenda": "1 = Sem energia · 5 = Muito disposto"},
            {"campo": "motivacao", "tipo": "escala",
             "texto": "Qual a sua motivação para o dia que começa?",
             "legenda": "1 = Nenhuma · 5 = Muito motivado"},
            {"campo": "ansiedade", "tipo": "escala",
             "texto": "Nível de ansiedade ao acordar / pensando no dia?",
             "legenda": "1 = Nenhuma · 5 = Muito forte"},
            {"campo": "leitura_biblia", "tipo": "opcoes",
             "texto": "Leu a Bíblia hoje?", "opcoes": SIM_NAO},
            {"campo": "oracao_manha", "tipo": "opcoes",
             "texto": "Teve seu momento de oração pela manhã?", "opcoes": SIM_NAO},
        ],
    },
    "tarde": {
        "titulo": "🌤️ Check-in da tarde",
        "perguntas": [
            {"campo": "estresse_tarde", "tipo": "escala",
             "texto": "Qual o seu nível de estresse agora?",
             "legenda": "1 = Tranquilo · 5 = Exausto/Extremo"},
            {"campo": "correria", "tipo": "escala",
             "texto": "Como está o nível de correria do seu dia?",
             "legenda": "1 = Calmo · 5 = Correria total"},
            {"campo": "sobrecarga", "tipo": "escala",
             "texto": "Sensação de sobrecarga: coisas demais para dar conta?",
             "legenda": "1 = Dou conta de boa · 5 = Sobrecarregado"},
            {"campo": "irritabilidade", "tipo": "escala",
             "texto": "Irritabilidade / paciência curta hoje até agora?",
             "legenda": "1 = Calmo · 5 = Muito irritado"},
            {"campo": "procrastinacao", "tipo": "escala",
             "texto": "Está adiando o que precisava fazer hoje?",
             "legenda": "1 = Nada · 5 = Muito"},
            {"campo": "sensacao_controle", "tipo": "escala",
             "texto": "Sensação de controle sobre o seu dia?",
             "legenda": "1 = Sem controle · 5 = Total controle"},
            {"campo": "imprevisto", "tipo": "imprevisto",
             "texto": "Houve algum imprevisto?", "opcoes": NAO_SIM},
        ],
    },
    "noite": {
        "titulo": "🌙 Fechamento do dia",
        "perguntas": [
            {"campo": "tristeza_desanimo", "tipo": "escala",
             "texto": "Tristeza / desânimo hoje?",
             "legenda": "1 = Ausente · 5 = Muito forte"},
            {"campo": "solidao", "tipo": "escala",
             "texto": "Sensação de solidão hoje?",
             "legenda": "1 = Bem acompanhado · 5 = Isolamento"},
            {"campo": "raiva", "tipo": "escala",
             "texto": "Raiva hoje?",
             "legenda": "1 = Nenhuma · 5 = Muito forte"},
            {"campo": "medo", "tipo": "escala",
             "texto": "Medo / insegurança hoje?",
             "legenda": "1 = Nenhum · 5 = Muito forte"},
            {"campo": "tempo_sozinho", "tipo": "texto", "min_campo": "tempo_sozinho_min",
             "texto": "Quanto tempo você ficou sozinho hoje? (ex: 3h 30m)"},
            {"campo": "pressao_social", "tipo": "escala",
             "texto": "Como se sentiu em relação à pressão social hoje (cobranças, comparação, expectativas)?",
             "legenda": "1 = Nenhuma pressão · 5 = Muita pressão"},
            {"campo": "alimentacao", "tipo": "escala",
             "texto": "Como foi sua alimentação hoje?",
             "legenda": "1 = Muito saudável · 5 = Péssima/excessos"},
            {"campo": "exercicio_fisico", "tipo": "opcoes",
             "texto": "Fez atividade física hoje?",
             "opcoes": [("✅ Sim", 1), ("😴 Não / Descanso", 0)]},
            {"campo": "descanso_dia", "tipo": "opcoes",
             "texto": "Fez pausas / descansou durante o dia?", "opcoes": SIM_NAO},
            {"campo": "estudou_leu", "tipo": "opcoes",
             "texto": "Estudou ou leu algo hoje (livro, curso, artigo)?", "opcoes": SIM_NAO},
            {"campo": "hobby_feito", "tipo": "opcoes",
             "texto": "Dedicou um tempo ao seu hobby hoje?", "opcoes": SIM_NAO},
            {"campo": "pornografia", "tipo": "opcoes",
             "texto": "Consumiu pornografia hoje?", "opcoes": NAO_SIM},
            {"campo": "habitos_ruins", "tipo": "imprevisto", "opcoes": NAO_SIM,
             "texto": "Bebida alcoólica ou outros hábitos ruins hoje?",
             "prompt": "Quais? (ex: álcool, cigarro, comer demais, virar a noite)"},
            {"campo": "culpa", "tipo": "escala", "min": 0, "max": 10,
             "texto": "Nível de culpa hoje?",
             "legenda": "0 = Nenhuma · 10 = Muito intensa"},
            {"campo": "produtividade", "tipo": "escala",
             "texto": "Quão produtivo você sentiu que foi hoje?",
             "legenda": "1 = Nada produtivo · 5 = Muito produtivo"},
            {"campo": "satisfacao", "tipo": "escala",
             "texto": "Satisfação com o seu dia e com você mesmo?",
             "legenda": "1 = Insatisfeito · 5 = Muito satisfeito"},
            {"campo": "tempo_tela", "tipo": "texto", "min_campo": "tempo_tela_min",
             "texto": "Quanto tempo de tela no celular hoje? (ex: 4h 30m)"},
            {"campo": "relato_livre", "tipo": "texto",
             "texto": "Relato livre: escreva como foi seu dia, sem filtro. 🤍"},
        ],
    },
}

CAMPOS = [p["campo"] for b in BLOCOS.values() for p in b["perguntas"]] + \
         [p["min_campo"] for b in BLOCOS.values() for p in b["perguntas"] if p.get("min_campo")]
CAMPOS_VALIDOS = set(CAMPOS)


def parse_tempo(texto: str):
    """'4h 30m' -> 270 | '4:30' -> 270 | '4h' -> 240 | '90m' -> 90 | '3' -> 180. None se não entender."""
    t = texto.strip().lower().replace(",", ".")
    if not t:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if m:
        return int(m[1]) * 60 + int(m[2])
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        v = float(t)
        return round(v * 60) if v <= 24 else round(v)
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*h(?:oras?)?)?\s*(?:(\d+)\s*(?:min|m)?)?", t)
    if m and (m[1] or m[2]):
        return round((float(m[1]) * 60 if m[1] else 0) + (int(m[2]) if m[2] else 0))
    return None


parse_tempo_tela = parse_tempo  # compatibilidade