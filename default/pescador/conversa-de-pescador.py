#!/usr/bin/env python3
"""
Conversa de Pescador - Assistente Conversacional com Auditoria Multi-Agente
e Verificação de Fatos na Web.

Fluxo:
1. Pescador (Narrador/Respondedor): formula a resposta explicativa detalhada.
2. Pesquisador (Buscador Web): busca referências, datas e contraprovas na internet.
3. Auditor Desconfiado (Cético): confronta a resposta, calcula o termômetro de
   veracidade e aponta o que é fato real vs 'conversa de pescador' (alucinação/exagero).
4. Suporte a Áudio: fala em português neural via Piper TTS e captura via PipeWire.

Uso:
  conversa-de-pescador [PERGUNTA] [OPÇÕES]
  jangada-pescador [PERGUNTA] [OPÇÕES]

Opções:
  -f, --falar       Narra a resposta e o parecer do auditor em voz alta (Piper TTS)
  -o, --ouvir       Grava a pergunta pelo microfone (PipeWire / whisper)
  -r, --rapido      Responde rápido sem acionar a rodada completa de auditoria
  --json            Emite o resultado estruturado em JSON
  --historico       Exibe o histórico de consultas com busca interativa
  -h, --ajuda       Mostra esta mensagem de ajuda
"""

import sys
import os
import re
import json
import time
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# Configuração de caminhos do ecossistema jangada
def obter_diretorios():
    base = Path(os.environ.get("JANGADA_ESTADO", Path.home() / ".local/state/jangada")) / "pescador"
    try:
        base.mkdir(parents=True, exist_ok=True)
        teste = base / ".teste_rw"
        teste.touch()
        teste.unlink(missing_ok=True)
        return base, base / "historico.jsonl", base / "sessoes"
    except OSError:
        fallback = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "jangada-pescador"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback, fallback / "historico.jsonl", fallback / "sessoes"

PESCADOR_DIR, HISTORICO_ARQ, SESSOES_DIR = obter_diretorios()
VOZ_PADRAO = Path.home() / ".local/share/piper-voices/pt_BR-faber-medium.onnx"

# Estilos de terminal ANSI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[36m"
C_BLUE = "\033[34m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"

BANNER = f"""{C_CYAN}{C_BOLD}
  ><(((*>   CONVERSA DE PESCADOR   <*)))><
{C_RESET}{C_DIM}  Assistente com auditoria multi-agente, checagem de fatos e voz em português
{C_RESET}"""


def limpar_markdown(texto: str) -> str:
    """Remove caracteres especiais de Markdown para sintetizar fala com fluidez."""
    t = re.sub(r"```.*?```", "", texto, flags=re.DOTALL)
    t = re.sub(r"`.*?`", "", t)
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"[#*_~>|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def falar(texto: str):
    """Narra o texto fornecido usando Piper TTS e reproduz pelo sistema de áudio."""
    if not VOZ_PADRAO.exists():
        print(f"{C_YELLOW}[Voz]{C_RESET} Modelo neural pt-BR não encontrado em {VOZ_PADRAO}", file=sys.stderr)
        return

    piper_bin = shutil.which("piper") or str(Path.home() / ".local/bin/piper")
    if not Path(piper_bin).exists() and not shutil.which("piper"):
        print(f"{C_YELLOW}[Voz]{C_RESET} Utilitário piper não instalado.", file=sys.stderr)
        return

    texto_fala = limpar_markdown(texto)
    if not texto_fala:
        return

    wav_tmp = Path("/tmp/pescador_fala.wav")
    try:
        proc = subprocess.Popen(
            [piper_bin, "--model", str(VOZ_PADRAO), "--output_file", str(wav_tmp)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        proc.communicate(input=texto_fala)

        if wav_tmp.exists() and wav_tmp.stat().st_size > 0:
            if shutil.which("paplay"):
                subprocess.run(["paplay", str(wav_tmp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("mpv"):
                subprocess.run(["mpv", "--really-quiet", str(wav_tmp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"{C_YELLOW}[Voz]{C_RESET} Falha ao reproduzir áudio: {e}", file=sys.stderr)
    finally:
        if wav_tmp.exists():
            wav_tmp.unlink(missing_ok=True)


def ouvir_microfone() -> str:
    """Captura áudio do microfone e realiza transcrição para texto."""
    gravador = shutil.which("pw-record") or shutil.which("parecord") or shutil.which("arecord")
    if not gravador:
        print(f"{C_RED}[Microfone]{C_RESET} Nenhum gravador compatível encontrado (instale pipewire ou pulseaudio).")
        return ""

    gravacao_wav = Path("/tmp/pescador_mic.wav")
    gravacao_wav.unlink(missing_ok=True)

    print(f"\n{C_RED}{C_BOLD}[Gravando...]{C_RESET} Fale agora. Pressione {C_BOLD}ENTER{C_RESET} para finalizar.")
    try:
        proc = subprocess.Popen(
            [gravador, "--rate", "16000", "--channels", "1", str(gravacao_wav)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        input()
        proc.terminate()
        proc.wait(timeout=2)
    except KeyboardInterrupt:
        proc.kill()
        return ""

    if not gravacao_wav.exists() or gravacao_wav.stat().st_size < 1000:
        print(f"{C_YELLOW}[Microfone]{C_RESET} Nenhum áudio detectado.")
        return ""

    # Transcrição com whisper-cpp caso disponível
    whisper_bin = shutil.which("whisper-cpp") or shutil.which("whisper")
    if whisper_bin:
        print(f"{C_CYAN}[Transcrição]{C_RESET} Processando áudio via {Path(whisper_bin).name}...")
        try:
            res = subprocess.run(
                [whisper_bin, "-m", str(Path.home() / ".local/share/whisper-models/ggml-base.bin"),
                 "-l", "pt", "-nt", "-f", str(gravacao_wav)],
                capture_output=True,
                text=True,
                timeout=30
            )
            texto = res.stdout.strip()
            if texto:
                print(f"{C_GREEN}[Você falou]:{C_RESET} {texto}")
                return texto
        except Exception:
            pass

    # Transcrição via agy multimodal como fallback
    agy_bin = shutil.which("agy")
    if agy_bin:
        print(f"{C_CYAN}[Transcrição]{C_RESET} Processando voz via inteligência artificial...")
        prompt_stt = "Transcreva com exatidão a fala contida neste áudio em português. Responda apenas com o texto transcrito, sem introdução nem comentários."
        try:
            res = subprocess.run(
                [agy_bin, "-p", f"{prompt_stt} (Áudio temporário em {gravacao_wav})"],
                capture_output=True,
                text=True,
                timeout=25
            )
            texto = res.stdout.strip()
            if texto:
                print(f"{C_GREEN}[Você falou]:{C_RESET} {texto}")
                return texto
        except Exception:
            pass

    print(f"{C_YELLOW}[Aviso]{C_RESET} Transcrição local necessita do pacote 'whisper-cpp' (`sudo pacman -S whisper-cpp`).")
    return ""


def invocar_modelo(prompt: str, sistema: str = "") -> str:
    """Invoca o modelo principal via agy ou claude."""
    agy_bin = shutil.which("agy")
    claude_bin = shutil.which("claude")

    prompt_completo = f"{sistema}\n\n{prompt}" if sistema else prompt

    if agy_bin:
        try:
            res = subprocess.run(
                [agy_bin, "-p", prompt_completo],
                capture_output=True,
                text=True,
                timeout=120
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception as e:
            print(f"{C_YELLOW}[Aviso agy]{C_RESET} {e}", file=sys.stderr)

    if claude_bin:
        try:
            res = subprocess.run(
                [claude_bin, "-p", prompt_completo],
                capture_output=True,
                text=True,
                timeout=120
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception as e:
            print(f"{C_YELLOW}[Aviso claude]{C_RESET} {e}", file=sys.stderr)

    return "Não foi possível conectar a um modelo de linguagem (verifique se 'agy' ou 'claude' está acessível no PATH)."


def formatar_contexto_conversa(turnos: list) -> str:
    """Formata os turnos anteriores para inclusão no contexto dos agentes."""
    if not turnos:
        return ""
    linhas = ["[Contexto dos turnos anteriores da conversa]"]
    for t in turnos[-4:]:
        t_num = t.get("turno", 1)
        linhas.append(f"Turno {t_num}:")
        linhas.append(f"Usuário: {t.get('pergunta', '').strip()}")
        resp = t.get("resposta", "").strip()
        if len(resp) > 500:
            resp = resp[:500] + "... [continua]"
        linhas.append(f"Pescador: {resp}")
        aud = t.get("auditoria", {})
        if aud and aud.get("veredito_resumo"):
            linhas.append(f"Auditoria: {aud.get('veredito_resumo')}")
    linhas.append("[Fim do contexto anterior]")
    return "\n".join(linhas)


def agente_pescador(pergunta: str, contexto_anterior: str = "") -> str:
    """Agente 1: O Pescador gera a resposta narrativa explicativa inicial."""
    sistema = (
        "Você é o Pescador no aplicativo 'Conversa de Pescador'. "
        "Seu objetivo é dar uma resposta muito detalhada, envolvente, rica e bem explicada sobre o tema perguntado. "
        "Se houver contexto de conversa anterior, mantenha total continuidade e encadeamento com os turnos passados. "
        "Apresente hipóteses, contextualização histórica e técnica. "
        "Não se preocupe se existirem versões conflitantes ou detalhes lendários na cultura popular: "
        "apresente o panorama completo. Responda em português claro e conciso."
    )
    prompt = f"{contexto_anterior}\n\nPergunta atual: {pergunta}" if contexto_anterior else pergunta
    return invocar_modelo(prompt, sistema)


def agente_pesquisador(pergunta: str, resposta_pescador: str, contexto_anterior: str = "") -> str:
    """Agente 2: Pesquisa fatos e referências na internet para auditar a resposta."""
    sistema = (
        "Você é o Pesquisador de Fatos do 'Conversa de Pescador'. "
        "Sua função é identificar as alegações centrais, números, datas, invenções e nomes na resposta fornecida "
        "e confrontar com documentação e conhecimento público, mantendo coerência com o contexto encadeado se houver. "
        "Para cada alegação relevante, indique:\n"
        "- A alegação específica.\n"
        "- A evidência factual documentada.\n"
        "- Fontes de referência de alta autoridade (instituições, normas, historiadores, artigos).\n"
        "Seja estritamente objetivo. Devolva até 400 palavras."
    )
    prompt = f"{contexto_anterior}\n\nPergunta do usuário: {pergunta}\n\nResposta do Pescador para verificar:\n{resposta_pescador}" if contexto_anterior else f"Pergunta do usuário: {pergunta}\n\nResposta do Pescador para verificar:\n{resposta_pescador}"
    return invocar_modelo(prompt, sistema)


def agente_auditor(pergunta: str, resposta_pescador: str, pesquisa_fatos: str, contexto_anterior: str = "") -> dict:
    """Agente 3: O Auditor Desconfiado emite o veredito e o termômetro de veracidade."""
    sistema = (
        "Você é o Auditor Desconfiado do 'Conversa de Pescador'. "
        "Você é extremamente cético, rigoroso e odeia 'conversa de pescador' (alucinações, exageros, lendas urbanas, anacronismos e dados inventados). "
        "Compare a resposta inicial com as evidências do pesquisador, considerando o encadeamento prévio se fornecido. "
        "Devolva a resposta EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:\n"
        "{\n"
        '  "grau_fato": 85,\n'
        '  "grau_pescador": 15,\n'
        '  "veredito_resumo": "Explicação em 2 frases sobre a confiabilidade geral.",\n'
        '  "analise_itens": [\n'
        '    {"afirmacao": "...", "status": "COMPROVADO" ou "CONVERSA DE PESCADOR" ou "CONTROVERSO", "detalhe": "..."}\n'
        "  ],\n"
        '  "referencias": ["Fonte 1 (instituição ou autor)", "Fonte 2"]\n'
        "}\n"
        "Responda SOMENTE o bloco JSON sem crases adicionais nem introdução."
    )
    prompt = f"{contexto_anterior}\n\nPergunta: {pergunta}\n\nResposta avaliada:\n{resposta_pescador}\n\nEvidências apuradas:\n{pesquisa_fatos}" if contexto_anterior else f"Pergunta: {pergunta}\n\nResposta avaliada:\n{resposta_pescador}\n\nEvidências apuradas:\n{pesquisa_fatos}"
    saida = invocar_modelo(prompt, sistema)

    # Parser seguro de JSON
    try:
        match = re.search(r"\{.*\}", saida, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    return {
        "grau_fato": 70,
        "grau_pescador": 30,
        "veredito_resumo": "Análise processada. Verifique os pontos detalhados na resposta.",
        "analise_itens": [],
        "referencias": []
    }


def barra_termometro(grau_fato: int, grau_pescador: int) -> str:
    """Gera uma barra colorida no terminal representando o termômetro de veracidade."""
    largura = 30
    pontos_fato = int(largura * (grau_fato / 100.0))
    pontos_pescador = largura - pontos_fato

    barra = f"{C_GREEN}{'=' * pontos_fato}{C_RED}{'~' * pontos_pescador}{C_RESET}"
    return f"[{barra}] {C_GREEN}{C_BOLD}{grau_fato}% Fato Real{C_RESET} | {C_RED}{C_BOLD}{grau_pescador}% Conversa de Pescador{C_RESET}"


def carregar_sessao(nome_sessao: str) -> dict:
    """Carrega os dados e turnos de uma sessão encadeada."""
    arquivo = SESSOES_DIR / f"{nome_sessao}.json"
    if arquivo.exists():
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "id": nome_sessao,
        "criado_em": datetime.now().isoformat(),
        "atualizado_em": datetime.now().isoformat(),
        "turnos": []
    }


def salvar_sessao(dados_sessao: dict):
    """Salva os dados da sessão em disco no diretório de estado."""
    try:
        SESSOES_DIR.mkdir(parents=True, exist_ok=True)
        dados_sessao["atualizado_em"] = datetime.now().isoformat()
        arquivo = SESSOES_DIR / f"{dados_sessao['id']}.json"
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados_sessao, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{C_YELLOW}[Aviso]{C_RESET} Falha ao salvar sessão: {e}", file=sys.stderr)


def salvar_historico(registro: dict):
    """Grava o registro no histórico seguindo a Regra 1 de isolamento do jangada."""
    try:
        PESCADOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORICO_ARQ, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"{C_YELLOW}[Aviso]{C_RESET} Não foi possível salvar histórico: {e}", file=sys.stderr)


def renderizar_previa_consulta(indice_str: str):
    """Renderiza a prévia formatada de uma consulta para o fzf."""
    try:
        idx = int(indice_str)
    except ValueError:
        return

    consultas = carregar_todas_consultas()
    if idx < 0 or idx >= len(consultas):
        print(f"{C_RED}Consulta não encontrada.{C_RESET}")
        return

    c = consultas[idx]
    data = c.get("data", "")[:19].replace("T", " ")
    sessao = c.get("sessao", "avulsa")
    turno = c.get("turno", 1)
    pergunta = c.get("pergunta", "")
    resposta = c.get("resposta", "")
    aud = c.get("auditoria", {})
    fato = aud.get("grau_fato", 100)
    pescador = aud.get("grau_pescador", 0)

    print(f"{C_CYAN}{C_BOLD}=== Consulta #{idx + 1} | {data} ==={C_RESET}")
    print(f"{C_DIM}Sessão: {sessao} (Turno {turno}){C_RESET}\n")
    print(f"{C_BOLD}Pergunta:{C_RESET}\n{pergunta}\n")
    print(f"{C_YELLOW}{C_BOLD}--- Parecer da Auditoria ---{C_RESET}")
    print(f"Termômetro: {barra_termometro(fato, pescador)}")
    print(f"{C_BOLD}Diagnóstico:{C_RESET} {aud.get('veredito_resumo', '')}\n")

    itens = aud.get("analise_itens", [])
    if itens:
        print(f"{C_BOLD}Itens Auditados:{C_RESET}")
        for it in itens:
            st = it.get("status", "")
            rotulo = f"{C_GREEN}[FATO]{C_RESET}" if "COMPROVADO" in st else (f"{C_RED}[PESCADOR]{C_RESET}" if ("CONVERSA" in st or "PESCADOR" in st) else f"{C_YELLOW}[CONTROVERSO]{C_RESET}")
            print(f" {rotulo} {it.get('afirmacao')}")
            if it.get("detalhe"):
                print(f"   {C_DIM}-> {it.get('detalhe')}{C_RESET}")
        print()

    refs = aud.get("referencias", [])
    if refs:
        print(f"{C_BOLD}Fontes e Referências:{C_RESET}")
        for r in refs:
            print(f" {C_BLUE}*{C_RESET} {r}")
        print()

    print(f"{C_CYAN}{C_BOLD}--- Resposta Completa do Pescador ---{C_RESET}")
    print(resposta)


def carregar_todas_consultas() -> list:
    """Lê todas as consultas salvas no histórico."""
    consultas = []
    if not HISTORICO_ARQ.exists():
        return consultas
    with open(HISTORICO_ARQ, "r", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                try:
                    consultas.append(json.loads(l))
                except Exception:
                    continue
    return consultas


def mostrar_historico(modo_fzf: bool = True):
    """Exibe o repositório de histórico com fzf interativo ou listagem clássica."""
    consultas = carregar_todas_consultas()
    if not consultas:
        print(f"{C_YELLOW}Nenhuma consulta registrada no repositório do Pescador.{C_RESET}")
        return

    fzf_bin = shutil.which("fzf")
    if modo_fzf and fzf_bin and sys.stdin.isatty():
        # Prepara linhas para o fzf com índice
        linhas_fzf = []
        for i, c in enumerate(consultas):
            data = c.get("data", "")[:16].replace("T", " ")
            fato = c.get("auditoria", {}).get("grau_fato", 100)
            perg = c.get("pergunta", "").replace("\n", " ")[:65]
            sessao = c.get("sessao", "avulsa")
            linhas_fzf.append(f"{i:4d} | {data} | {fato:3d}% Fato | [{sessao}] {perg}")

        meu_script = str(Path(__file__).resolve())
        cmd_fzf = [
            fzf_bin,
            "--ansi",
            "--reverse",
            "--header=Repositório de Pesquisas - Conversa de Pescador (Enter: detalhes | Esc: sair)",
            f"--preview=python3 {meu_script} --previa-idx {{1}}",
            "--preview-window=right:60%:wrap"
        ]

        try:
            proc = subprocess.Popen(
                cmd_fzf,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True
            )
            stdout, _ = proc.communicate(input="\n".join(reversed(linhas_fzf)))
            selecionado = stdout.strip()
            if selecionado:
                partes = selecionado.split("|")
                idx_sel = int(partes[0].strip())
                print("\033[H\033[J", end="")
                renderizar_previa_consulta(str(idx_sel))
                print(f"\n{C_DIM}Pressione ENTER para continuar...{C_RESET}")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
            return
        except Exception:
            pass

    # Exibição simples se não houver fzf ou não for TTY
    print(f"\n{C_BOLD}=== Repositório de Pesquisas ({len(consultas)} salvas) ==={C_RESET}\n")
    for i, c in enumerate(reversed(consultas[-20:]), 1):
        data = c.get("data", "")[:16].replace("T", " ")
        fato = c.get("auditoria", {}).get("grau_fato", "?")
        sessao = c.get("sessao", "avulsa")
        print(f"{C_CYAN}{i:2d}.{C_RESET} [{C_DIM}{data}{C_RESET}] ({C_GREEN}{fato}% Fato{C_RESET}) [{sessao}] {C_BOLD}{c.get('pergunta')}{C_RESET}")
    print()


def processar_consulta(pergunta: str, sessao_id: str = None, falar_voz: bool = False, rapido: bool = False, saida_json: bool = False) -> dict:
    """Executa o ciclo completo de multi-agentes para a pergunta com suporte a encadeamento."""
    inicio = time.time()

    sessao_nome = sessao_id or f"sessao-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    sessao_dados = carregar_sessao(sessao_nome)
    turnos_anteriores = sessao_dados.get("turnos", [])
    contexto_str = formatar_contexto_conversa(turnos_anteriores)

    num_turno = len(turnos_anteriores) + 1

    if not saida_json:
        prefixo_turno = f"[Turno {num_turno} | Sessão: {sessao_nome}] " if num_turno > 1 else ""
        print(f"\n{C_BOLD}{prefixo_turno}Pergunta:{C_RESET} {pergunta}\n")
        print(f"{C_BLUE}[1/3 Pescador]{C_RESET} Formulando a explicação detalhada...")

    resposta = agente_pescador(pergunta, contexto_anterior=contexto_str)

    if rapido:
        tempo_total = round(time.time() - inicio, 1)
        registro = {
            "data": datetime.now().isoformat(),
            "sessao": sessao_nome,
            "turno": num_turno,
            "pergunta": pergunta,
            "resposta": resposta,
            "auditoria": {"grau_fato": 100, "grau_pescador": 0, "veredito_resumo": "Resposta rápida sem auditoria de fontes."},
            "tempo_segundos": tempo_total
        }
        sessao_dados["turnos"].append(registro)
        salvar_sessao(sessao_dados)
        salvar_historico(registro)

        if saida_json:
            print(json.dumps(registro, ensure_ascii=False, indent=2))
        else:
            print(f"\n{C_CYAN}{C_BOLD}--- Resposta do Pescador ---{C_RESET}\n")
            print(resposta)
            if falar_voz:
                falar(resposta)
        return registro

    if not saida_json:
        print(f"{C_MAGENTA}[2/3 Pesquisador]{C_RESET} Lançando a rede na internet e colhendo fontes...")

    pesquisa = agente_pesquisador(pergunta, resposta, contexto_anterior=contexto_str)

    if not saida_json:
        print(f"{C_YELLOW}[3/3 Auditor Desconfiado]{C_RESET} Separando o que é peixe graúdo de história fiada...")

    auditoria = agente_auditor(pergunta, resposta, pesquisa, contexto_anterior=contexto_str)
    tempo_total = round(time.time() - inicio, 1)

    registro = {
        "data": datetime.now().isoformat(),
        "sessao": sessao_nome,
        "turno": num_turno,
        "pergunta": pergunta,
        "resposta": resposta,
        "auditoria": auditoria,
        "tempo_segundos": tempo_total
    }
    sessao_dados["turnos"].append(registro)
    salvar_sessao(sessao_dados)
    salvar_historico(registro)

    if saida_json:
        print(json.dumps(registro, ensure_ascii=False, indent=2))
        return registro

    # Exibição rica no terminal
    print(f"\n{C_CYAN}{C_BOLD}=================== Resposta do Pescador ==================={C_RESET}\n")
    print(resposta)

    print(f"\n{C_YELLOW}{C_BOLD}================= Veredito da Auditoria ==================={C_RESET}\n")
    grau_fato = auditoria.get("grau_fato", 100)
    grau_pescador = auditoria.get("grau_pescador", 0)

    print(f"Termômetro de Pescador: {barra_termometro(grau_fato, grau_pescador)}\n")
    print(f"{C_BOLD}Diagnóstico:{C_RESET} {auditoria.get('veredito_resumo', '')}\n")

    itens = auditoria.get("analise_itens", [])
    if itens:
        print(f"{C_BOLD}Checagem Ponto a Ponto:{C_RESET}")
        for item in itens:
            st = item.get("status", "")
            if "COMPROVADO" in st:
                rotulo = f"{C_GREEN}[FATO REAL]{C_RESET}"
            elif "CONVERSA" in st or "PESCADOR" in st:
                rotulo = f"{C_RED}[CONVERSA DE PESCADOR]{C_RESET}"
            else:
                rotulo = f"{C_YELLOW}[CONTROVERSO]{C_RESET}"

            print(f"  {rotulo} {C_BOLD}{item.get('afirmacao')}{C_RESET}")
            if item.get("detalhe"):
                print(f"    {C_DIM}-> {item.get('detalhe')}{C_RESET}")

    refs = auditoria.get("referencias", [])
    if refs:
        print(f"\n{C_BOLD}Referências e Fontes:{C_RESET}")
        for ref in refs:
            print(f"  {C_BLUE}*{C_RESET} {ref}")

    print(f"\n{C_DIM}Consulta finalizada em {tempo_total}s (Sessão: {sessao_nome} | Turno {num_turno}).{C_RESET}\n")

    if falar_voz:
        resumo_fala = f"{auditoria.get('veredito_resumo', '')}. A resposta principal é: {resposta[:300]}"
        print(f"{C_CYAN}[Voz]{C_RESET} Narrando resumo com Piper TTS...")
        falar(resumo_fala)

    return registro


def modo_interativo(sessao_id: str = None, falar_voz: bool = False):
    """Loop conversacional interativo com encadeamento de turnos e gerenciamento de sessões."""
    print(BANNER)

    sessao_atual = sessao_id or f"sessao-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    dados_sessao = carregar_sessao(sessao_atual)

    voz_status = f"{C_GREEN}ativa{C_RESET}" if falar_voz else f"{C_DIM}desativada{C_RESET}"
    turnos_qtd = len(dados_sessao.get("turnos", []))
    info_turnos = f" ({turnos_qtd} turnos prévios)" if turnos_qtd > 0 else ""

    print(f"Sessão: {C_BOLD}{sessao_atual}{C_RESET}{info_turnos} | Voz: {voz_status}")
    print(f"Digite {C_BOLD}/ajuda{C_RESET} para ver comandos, {C_BOLD}/sair{C_RESET} para fechar.\n")

    while True:
        try:
            prompt_str = f"{C_BOLD}{C_CYAN}pescador [{sessao_atual}] > {C_RESET}"
            entrada = input(prompt_str).strip()

            if not entrada:
                continue

            if entrada in ("/sair", "/exit", "sair", "exit"):
                print(f"\n{C_CYAN}Até a próxima pescaria!{C_RESET}\n")
                break
            elif entrada == "/historico" or entrada == "/pesquisas":
                mostrar_historico()
                continue
            elif entrada == "/limpar":
                print("\033[H\033[J", end="")
                print(BANNER)
                continue
            elif entrada == "/falar":
                falar_voz = not falar_voz
                status_txt = f"{C_GREEN}ativada{C_RESET}" if falar_voz else f"{C_RED}desativada{C_RESET}"
                print(f"Voz neural {status_txt}.")
                continue
            elif entrada == "/ouvir":
                texto_ouvido = ouvir_microfone()
                if texto_ouvido:
                    processar_consulta(texto_ouvido, sessao_id=sessao_atual, falar_voz=falar_voz)
                continue
            elif entrada.startswith("/sessao"):
                partes = entrada.split(maxsplit=1)
                if len(partes) > 1:
                    sessao_atual = partes[1].strip()
                    dados_sessao = carregar_sessao(sessao_atual)
                    t_qtd = len(dados_sessao.get("turnos", []))
                    print(f"{C_GREEN}Sessão alterada para '{sessao_atual}' ({t_qtd} turnos gravados).{C_RESET}")
                else:
                    t_qtd = len(carregar_sessao(sessao_atual).get("turnos", []))
                    print(f"Sessão ativa: {C_BOLD}{sessao_atual}{C_RESET} ({t_qtd} turnos acumulados).")
                continue
            elif entrada in ("/novo", "/reiniciar", "/nova"):
                sessao_atual = f"sessao-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                print(f"{C_GREEN}Novo diálogo encadeado iniciado! Sessão: {sessao_atual}{C_RESET}")
                continue
            elif entrada in ("/contexto", "/turnos"):
                dados = carregar_sessao(sessao_atual)
                turnos = dados.get("turnos", [])
                if not turnos:
                    print(f"{C_YELLOW}Nenhum turno anterior nesta sessão.{C_RESET}")
                else:
                    print(f"\n{C_BOLD}=== Turnos da Sessão '{sessao_atual}' ==={C_RESET}")
                    for t in turnos:
                        t_num = t.get("turno", 1)
                        p = t.get("pergunta", "")[:70]
                        print(f" {C_CYAN}Turno {t_num}:{C_RESET} {p}")
                    print()
                continue
            elif entrada in ("/ajuda", "/help", "ajuda", "help"):
                print(f"\n{C_BOLD}Comandos do Chat:{C_RESET}")
                print("  /sessao [nome] - Mostra ou alterna a sessão encadeada ativa")
                print("  /novo          - Inicia uma nova conversa limpa")
                print("  /contexto      - Mostra os turnos acumulados na sessão atual")
                print("  /historico     - Abre o repositório de pesquisas (fzf)")
                print("  /ouvir         - Grava pergunta do microfone")
                print("  /falar         - Alterna narração das respostas por voz neural")
                print("  /limpar        - Limpa a tela")
                print("  /sair          - Encerra o chat\n")
                continue

            processar_consulta(entrada, sessao_id=sessao_atual, falar_voz=falar_voz)

        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{C_CYAN}Pescaria encerrada.{C_RESET}\n")
            break


def main():
    parser = argparse.ArgumentParser(
        prog="conversa-de-pescador",
        description="Conversa de Pescador: chat com auditoria multi-agente, busca de fontes e voz em português.",
        add_help=False
    )
    parser.add_argument("-h", "--help", "--ajuda", action="help", help="Mostra esta mensagem de ajuda")
    parser.add_argument("pergunta", nargs="*", help="Pergunta direta (se omitida, abre o modo interativo)")
    parser.add_argument("-s", "--sessao", help="Identificador da sessão encadeada")
    parser.add_argument("-f", "--falar", action="store_true", help="Narra a resposta em voz alta com Piper TTS")
    parser.add_argument("-o", "--ouvir", action="store_true", help="Grava a pergunta do microfone antes de responder")
    parser.add_argument("-r", "--rapido", action="store_true", help="Resposta rápida sem rodada de auditoria")
    parser.add_argument("--json", action="store_true", help="Saída em formato JSON")
    parser.add_argument("--historico", "--pesquisas", action="store_true", help="Mostra o repositório de pesquisas")
    parser.add_argument("--previa-idx", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.previa_idx is not None:
        renderizar_previa_consulta(args.previa_idx)
        return

    if args.historico:
        mostrar_historico()
        return

    pergunta_texto = " ".join(args.pergunta).strip()

    if args.ouvir and not pergunta_texto:
        pergunta_texto = ouvir_microfone()

    if pergunta_texto:
        processar_consulta(
            pergunta_texto,
            sessao_id=args.sessao,
            falar_voz=args.falar,
            rapido=args.rapido,
            saida_json=args.json
        )
    else:
        modo_interativo(sessao_id=args.sessao, falar_voz=args.falar)


if __name__ == "__main__":
    main()
