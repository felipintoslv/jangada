"""Gera registros de exemplo de subagentes e delegações.

Uso: python3 testes/amostras-subagentes.py RAIZ PASTA [INICIO]

INICIO (ISO 8601) é o horário da primeira linha; o padrão é 27/09/2026 10h UTC.

Em RAIZ/claude/projects: uma conversa em PASTA, com uma resposta da conversa
principal (1.000 tokens sem o cache lido) e três subagentes do Claude:
  a1  explorador, primeiro plano: totais e retorno no tool_result;
  a2  general-purpose "Revisar a entrega", segundo plano: totais no aviso
      de tarefa, relatório no SubagentHandback, uma edição (Edit);
  a3  sessão antiga: sem totais nem retorno na conversa mãe.
Em RAIZ/agy: um subagente "self" (Code Reviewer) com 5 passos, um de
escrita. Em RAIZ/state/jangada/delegacoes.jsonl: uma delegação atendida e
uma recusada por cota.
"""
import datetime
import json
import os
import re
import sqlite3
import sys

raiz, pasta = sys.argv[1], sys.argv[2]
# A pasta de projeto do Claude tem o caminho com "-" no lugar de cada sinal.
proj = os.path.join(raiz, "claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(pasta)))
subs = os.path.join(proj, "sess1", "subagents")
os.makedirs(subs, exist_ok=True)
base = datetime.datetime.fromisoformat(sys.argv[3] if len(sys.argv) > 3 else "2026-09-27T10:00:00+00:00")


def T(minutos):
    return (base + datetime.timedelta(minutes=minutos)).isoformat()


def gravar(caminho, linhas):
    with open(caminho, "w", encoding="utf-8") as f:
        for d in linhas:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def conversa(agente, ferramenta=None, uso=1000):
    linhas = [{"type": "user", "isSidechain": True, "agentId": agente, "cwd": pasta, "timestamp": T(1),
               "message": {"role": "user", "content": "Revise a entrega" if agente == "a2" else "Mapeie"}}]
    conteudo = [{"type": "text", "text": "ok"}]
    if ferramenta:
        conteudo.append({"type": "tool_use", "id": "t1", "name": ferramenta, "input": {}})
    linhas.append({"type": "assistant", "isSidechain": True, "agentId": agente, "cwd": pasta,
                   "timestamp": T(2),
                   "message": {"id": "m-" + agente, "role": "assistant", "content": conteudo,
                               "usage": {"input_tokens": 10, "output_tokens": uso,
                                         "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}})
    return linhas


metas = {
    "a1": {"agentType": "explorador", "description": "Mapear o validar", "toolUseId": "toolu_fg",
           "spawnDepth": 1, "requestShape": "foreground"},
    "a2": {"agentType": "general-purpose", "description": "Revisar a entrega", "toolUseId": "toolu_bg",
           "spawnDepth": 1, "requestShape": "background"},
    "a3": {"agentType": "general-purpose", "description": "Contar linhas", "toolUseId": "toolu_velho",
           "spawnDepth": 1},
}
for a, m in metas.items():
    json.dump(m, open(os.path.join(subs, f"agent-{a}.meta.json"), "w"))
gravar(os.path.join(subs, "agent-a1.jsonl"), conversa("a1", "Grep"))
gravar(os.path.join(subs, "agent-a2.jsonl"), conversa("a2", "Edit"))
gravar(os.path.join(subs, "agent-a3.jsonl"), conversa("a3", uso=490))

retorno_a1 = "Achei em bin/jangada-validar:82 a função registrar.\n" * 8
relatorio_a2 = "Nada a apontar na entrega.\n" * 20
gravar(os.path.join(proj, "sess1.jsonl"), [
    {"type": "user", "cwd": pasta, "timestamp": T(0), "message": {"role": "user", "content": "tarefa"}},
    # A mesma resposta em duas linhas: conta uma vez, com o uso da última.
    {"type": "assistant", "cwd": pasta, "timestamp": T(0), "message": {"id": "m-mae", "role": "assistant",
     "content": [], "usage": {"input_tokens": 100, "output_tokens": 1, "cache_read_input_tokens": 7000}}},
    {"type": "assistant", "cwd": pasta, "timestamp": T(0), "message": {"id": "m-mae", "role": "assistant",
     "content": [], "usage": {"input_tokens": 100, "output_tokens": 400, "cache_creation_input_tokens": 500,
                              "cache_read_input_tokens": 7000}}},
    {"type": "user", "cwd": pasta, "timestamp": T(3),
     "toolUseResult": {"status": "completed", "totalTokens": 20000, "totalDurationMs": 5000,
                       "totalToolUseCount": 3, "content": [{"type": "text", "text": retorno_a1}]},
     "message": {"role": "user", "content": [{"tool_use_id": "toolu_fg", "type": "tool_result",
                                              "content": [{"type": "text", "text": retorno_a1}]}]}},
    {"type": "user", "cwd": pasta, "timestamp": T(3),
     "toolUseResult": {"isAsync": True, "status": "async_launched", "agentId": "a2"},
     "message": {"role": "user", "content": [{"tool_use_id": "toolu_bg", "type": "tool_result",
                                              "content": [{"type": "text", "text": "Async agent launched"}]}]}},
    {"type": "user", "cwd": pasta, "timestamp": T(4),
     "message": {"role": "user", "content": "Another Claude session sent a message:\n"
                 "<agent-message from=\"a2\">\n" + relatorio_a2 + "</agent-message>"}},
    {"type": "attachment", "cwd": pasta, "timestamp": T(4),
     "attachment": {"type": "queued_command", "usage": {"totalTokens": 50000, "toolUses": 7, "durationMs": 9000},
                    "prompt": "<task-notification>\n<task-id>a2</task-id>\n<status>completed</status>\n"
                              "<result>This agent's report was delivered to you as a message from \"a2\" "
                              "(its SubagentHandback call).</result>\n</task-notification>"}},
])

brain = os.path.join(raiz, "agy", "brain", "c1", ".system_generated", "subagents")
os.makedirs(brain, exist_ok=True)
json.dump({"conversationId": "s1", "subagentDescriptor": {"typeName": "self", "role": "Code Reviewer"},
           "state": "SUBAGENT_STATE_DONE", "spawnStepIndex": 4, "workspaceUris": ["file://" + pasta]},
          open(os.path.join(brain, "s1.json"), "w"))
# O início do subagente do agy é a data do arquivo.
os.utime(os.path.join(brain, "s1.json"), (base.timestamp() + 60,) * 2)
conv = os.path.join(raiz, "agy", "conversations")
os.makedirs(conv, exist_ok=True)
con = sqlite3.connect(os.path.join(conv, "s1.db"))
con.execute("create table steps (idx integer, step_type integer, step_payload blob)")
for i, carga in enumerate([b"view_file a.sh", b"grep_search x", b"write_to_file b.sh", b"texto", b""]):
    con.execute("insert into steps values (?, ?, ?)", (i, 14, carga))
con.commit()
con.close()

estado = os.path.join(raiz, "state", "jangada")
os.makedirs(estado, exist_ok=True)
comum = {"sessao": "s", "projeto": "proj", "pasta": pasta, "modelo": "gemini-3.8-flash-low", "segundos": 40}
gravar(os.path.join(estado, "delegacoes.jsonl"), [
    dict(comum, data=T(5), papel="explorador", destino="agy", codigo_saida=0,
         palavras=80, tokens_retorno=100, passos=12, tokens_agy=9000, cota_antes=93.5, cota_depois=93.1,
         recusa=False, motivo="", conversa="d1"),
    dict(comum, data=T(6), papel="leitor", destino="agy", codigo_saida=4,
         palavras=0, tokens_retorno=20, passos=None, tokens_agy=None, cota_antes=15.0, cota_depois=None,
         recusa=True, motivo="cota de 5 horas do Gemini em 15%, abaixo de 20%", conversa=""),
])
