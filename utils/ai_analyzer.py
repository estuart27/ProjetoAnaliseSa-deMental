"""Resumo semanal com Gemini cruzando sono, estresse, humor, hábitos, eventos e /espaco."""
import asyncio
import json
import logging
import statistics

import config
import database

log = logging.getLogger(__name__)

SYSTEM = """Você é um assistente de autoacompanhamento de saúde emocional, em português do Brasil.
Você recebe os registros diários de UMA pessoa (escalas de 1 a 5, hábitos, eventos e anotações do /espaco).
Regras:
- Tom acolhedor, direto e honesto. Sem julgamento. Nada de diagnósticos e nada de prometer cura.
- Aponte padrões e cruzamentos reais nos dados (ex.: sono ruim -> estresse no dia; correria/pressão social
  e tristeza/solidão; tempo sozinho e tempo de tela; impacto de bons hábitos como bíblia, oração, treino,
  estudo/leitura, pausas e hobby vs. hábitos ruins/pornografia). Seja cauteloso: poucos dias = correlação fraca.
- Cruze também os relatos, eventos da linha do tempo e anotações do /espaco para dar contexto humano.
- Cite números concretos (médias, melhores/piores dias). Diga quando faltarem dados.
- Valorize o que está indo bem antes dos pontos de atenção.
- Termine com 2 a 3 ações práticas e pequenas para a próxima semana.
- Se houver tristeza/solidão >= 4 por vários dias, relatos de desesperança, ou qualquer sinal de risco,
  incentive com carinho a conversar com um psicólogo/psiquiatra e com alguém de confiança. Se houver menção
  a pensamentos de se machucar, lembre que no Brasil o CVV atende 24h pelo 188.
- Máximo ~280 palavras. Texto simples (sem markdown pesado), pode usar poucos emojis.
Escalas: sono 1=péssimo..5=excelente | estresse 1=tranquilo..5=extremo | tristeza 1=ausente..5=muito forte |
solidão 1=bem acompanhado..5=isolamento | alimentação 1=muito saudável..5=péssima |
correria 1=calmo..5=correria total | pressão social 1=nenhuma..5=muita.
Booleanos: 1=sim, 0=não."""

CAMPOS_ANALISE = [
    "data", "sono_qualidade", "leitura_biblia", "oracao_manha", "estresse_tarde", "correria",
    "imprevisto", "tristeza_desanimo", "solidao", "tempo_sozinho_min", "pressao_social",
    "alimentacao", "exercicio_fisico", "descanso_dia", "estudou_leu", "hobby_feito",
    "pornografia", "habitos_ruins", "tempo_tela_min", "relato_livre",
]


def _media(registros, campo):
    vals = [r[campo] for r in registros if r.get(campo) is not None]
    return round(statistics.mean(vals), 2) if vals else None


def _correlacao(registros, a, b):
    pares = [(r[a], r[b]) for r in registros if r.get(a) is not None and r.get(b) is not None]
    if len(pares) < 4:
        return None
    xs, ys = zip(*pares)
    try:
        return round(statistics.correlation(xs, ys), 2)
    except statistics.StatisticsError:
        return None


def _montar_prompt(registros, notas_espaco, eventos) -> str:
    dados = [{k: r.get(k) for k in CAMPOS_ANALISE} for r in registros]
    resumo = {
        "dias_com_registro": len(registros),
        "medias": {
            c: _media(registros, c)
            for c in (
                "sono_qualidade", "estresse_tarde", "tristeza_desanimo", "solidao",
                "alimentacao", "correria", "pressao_social", "tempo_sozinho_min", "tempo_tela_min",
            )
        },
        "correlacoes": {
            "sono_x_estresse": _correlacao(registros, "sono_qualidade", "estresse_tarde"),
            "sono_x_tristeza": _correlacao(registros, "sono_qualidade", "tristeza_desanimo"),
            "estresse_x_tristeza": _correlacao(registros, "estresse_tarde", "tristeza_desanimo"),
            "correria_x_estresse": _correlacao(registros, "correria", "estresse_tarde"),
            "pressao_x_tristeza": _correlacao(registros, "pressao_social", "tristeza_desanimo"),
            "tela_x_tristeza": _correlacao(registros, "tempo_tela_min", "tristeza_desanimo"),
        },
        "eventos_linha_do_tempo": eventos,
        "anotacoes_espaco": notas_espaco,
    }
    return (
        "Analise a semana abaixo.\n\n"
        f"ESTATÍSTICAS E CONTEXTO:\n{json.dumps(resumo, ensure_ascii=False)}\n\n"
        f"REGISTROS DIÁRIOS (null = não respondido):\n{json.dumps(dados, ensure_ascii=False)}"
    )


def _chamar_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.4),
    )
    return (resp.text or "").strip()


async def gerar_resumo_semanal(dias: int = 7) -> str:
    if not config.GEMINI_API_KEY:
        return "⚠️ GEMINI_API_KEY não configurada no .env."
    serie = database.get_serie(dias)
    registros = [r for r in serie if any(r.get(c) is not None for c in CAMPOS_ANALISE if c != "data")]
    notas_espaco = database.listar_espaco(dias=dias, limite=30)
    eventos = database.listar_eventos(dias=dias)

    if len(registros) < 2 and not notas_espaco:
        return "Ainda tenho poucos dias registrados para analisar. Continue respondendo e em breve chega seu resumo. 🌱"
    try:
        texto = await asyncio.to_thread(_chamar_gemini, _montar_prompt(registros, notas_espaco, eventos))
        return texto or "A IA não retornou texto. Tente de novo em instantes."
    except Exception:
        log.exception("Erro ao consultar o Gemini")
        return "⚠️ Não consegui gerar o resumo agora (erro ao falar com o Gemini). Veja os logs."