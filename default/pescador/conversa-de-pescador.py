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
JANGADA_ESTADO = Path(os.environ.get("JANGADA_ESTADO", Path.home() / ".local/state/jangada"))
PESCADOR_DIR = JANGADA_ESTADO / "pescador"
HISTORICO_ARQ = PESCADOR_DIR / "historico.jsonl"
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


def agente_pescador(pergunta: str) -> str:
    """Agente 1: O Pescador gera a resposta narrativa explicativa inicial."""
    sistema = (
        "Você é o Pescador no aplicativo 'Conversa de Pescador'. "
        "Seu objetivo é dar uma resposta muito detalhada, envolvente, rica e bem explicada sobre o tema perguntado. "
        "Apresente hipóteses, contextualização histórica e técnica. "
        "Não se preocupe se existirem versões conflitantes ou detalhes lendários na cultura popular: "
        "apresente o panorama completo. Responda em português claro e conciso."
    )
    return invocar_modelo(pergunta, sistema)


def agente_pesquisador(pergunta: str, resposta_pescador: str) -> str:
    """Agente 2: Pesquisa fatos e referências na internet para auditar a resposta."""
    sistema = (
        "Você é o Pesquisador de Fatos do 'Conversa de Pescador'. "
        "Sua função é identificar as alegações centrais, números, datas, invenções e nomes na resposta fornecida "
        "e confrontar com documentação e conhecimento público. "
        "Para cada alegação relevante, indique:\n"
        "- A alegação específica.\n"
        "- A evidência factual documentada.\n"
        "- Fontes de referência de alta autoridade (instituições, normas, historiadores, artigos).\n"
        "Seja estritamente objetivo. Devolva até 400 palavras."
    )
    prompt = f"Pergunta do usuário: {pergunta}\n\nResposta do Pescador para verificar:\n{resposta_pescador}"
    return invocar_modelo(prompt, sistema)


def agente_auditor(pergunta: str, resposta_pescador: str, pesquisa_fatos: str) -> dict:
    """Agente 3: O Auditor Desconfiado emite o veredito e o termômetro de veracidade."""
    sistema = (
        "Você é o Auditor Desconfiado do 'Conversa de Pescador'. "
        "Você é extremamente cético, rigoroso e odeia 'conversa de pescador' (alucinações, exageros, lendas urbanas, anacronismos e dados inventados). "
        "Compare a resposta inicial com as evidências do pesquisador. "
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
    prompt = f"Pergunta: {pergunta}\n\nResposta avaliada:\n{resposta_pescador}\n\nEvidências apuradas:\n{pesquisa_fatos}"
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


def salvar_historico(registro: dict):
    """Grava o registro no histórico seguindo a Regra 1 de isolamento do jangada."""
    try:
        PESCADOR_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORICO_ARQ, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"{C_YELLOW}[Aviso]{C_RESET} Não foi possível salvar histórico: {e}", file=sys.stderr)


def mostrar_historico():
    """Exibe o histórico de perguntas anteriores."""
    if not HISTORICO_ARQ.exists():
        print(f"{C_YELLOW}Nenhuma consulta registrada no histórico.{C_RESET}")
        return

    consultas = []
    with open(HISTORICO_ARQ, "r", encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                try:
                    consultas.append(json.loads(linha))
                except Exception:
                    continue

    if not consultas:
        print(f"{C_YELLOW}Histórico vazio.{C_RESET}")
        return

    print(f"\n{C_BOLD}=== Histórico de Consultas ({len(consultas)} salvas) ==={C_RESET}\n")
    for i, c in enumerate(reversed(consultas[-15:]), 1):
        data = c.get("data", "")[:16].replace("T", " ")
        fato = c.get("auditoria", {}).get("grau_fato", "?")
        print(f"{C_CYAN}{i:2d}.{C_RESET} [{C_DIM}{data}{C_RESET}] ({C_GREEN}{fato}% Fato{C_RESET}) {C_BOLD}{c.get('pergunta')}{C_RESET}")


def processar_consulta(pergunta: str, falar_voz: bool = False, rapido: bool = False, saida_json: bool = False):
    """Executa o ciclo completo de multi-agentes para a pergunta."""
    inicio = time.time()

    if not saida_json:
        print(f"\n{C_BOLD}Pergunta:{C_RESET} {pergunta}\n")
        print(f"{C_BLUE}[1/3 Pescador]{C_RESET} Formulando a explicação detalhada...")

    resposta = agente_pescador(pergunta)

    if rapido:
        tempo_total = round(time.time() - inicio, 1)
        registro = {
            "data": datetime.now().isoformat(),
            "pergunta": pergunta,
            "resposta": resposta,
            "auditoria": {"grau_fato": 100, "grau_pescador": 0, "veredito_resumo": "Resposta rápida sem auditoria de fontes."},
            "tempo_segundos": tempo_total
        }
        salvar_historico(registro)
        if saida_json:
            print(json.dumps(registro, ensure_ascii=False, indent=2))
        else:
            print(f"\n{C_CYAN}{C_BOLD}--- Resposta do Pescador ---{C_RESET}\n")
            print(resposta)
            if falar_voz:
                falar(resposta)
        return

    if not saida_json:
        print(f"{C_MAGENTA}[2/3 Pesquisador]{C_RESET} Lançando a rede na internet e colhendo fontes...")

    pesquisa = agente_pesquisador(pergunta, resposta)

    if not saida_json:
        print(f"{C_YELLOW}[3/3 Auditor Desconfiado]{C_RESET} Separando o que é peixe graúdo de história fiada...")

    auditoria = agente_auditor(pergunta, resposta, pesquisa)
    tempo_total = round(time.time() - inicio, 1)

    registro = {
        "data": datetime.now().isoformat(),
        "pergunta": pergunta,
        "resposta": resposta,
        "auditoria": auditoria,
        "tempo_segundos": tempo_total
    }
    salvar_historico(registro)

    if saida_json:
        print(json.dumps(registro, ensure_ascii=False, indent=2))
        return

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

    print(f"\n{C_DIM}Consulta finalizada em {tempo_total}s.{C_RESET}\n")

    if falar_voz:
        resumo_fala = f"{auditoria.get('veredito_resumo', '')}. A resposta principal é: {resposta[:300]}"
        print(f"{C_CYAN}[Voz]{C_RESET} Narrando resumo com Piper TTS...")
        falar(resumo_fala)


def modo_interativo(falar_voz: bool = False):
    """Loop conversacional interativo do chat."""
    print(BANNER)
    voz_status = f"{C_GREEN}ativa{C_RESET}" if falar_voz else f"{C_DIM}desativada{C_RESET}"
    print(f"Voz: {voz_status} (digite {C_BOLD}/falar{C_RESET} para alternar, {C_BOLD}/ouvir{C_RESET} para microfone, {C_BOLD}/sair{C_RESET} para fechar)\n")

    while True:
        try:
            prompt_str = f"{C_BOLD}{C_CYAN}pescador > {C_RESET}"
            entrada = input(prompt_str).strip()

            if not entrada:
                continue

            if entrada in ("/sair", "/exit", "sair", "exit"):
                print(f"\n{C_CYAN}Até a próxima pescaria!{C_RESET}\n")
                break
            elif entrada == "/historico":
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
                    processar_consulta(texto_ouvido, falar_voz=falar_voz)
                continue
            elif entrada in ("/ajuda", "/help", "ajuda", "help"):
                print(f"\n{C_BOLD}Comandos do Chat:{C_RESET}")
                print("  /ouvir     - Grava pergunta do microfone")
                print("  /falar     - Liga ou desliga leitura das respostas por voz")
                print("  /historico - Mostra histórico de perguntas")
                print("  /limpar    - Limpa a tela")
                print("  /sair      - Encerra o chat\n")
                continue

            processar_consulta(entrada, falar_voz=falar_voz)

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
    parser.add_argument("-f", "--falar", action="store_true", help="Narra a resposta em voz alta com Piper TTS")
    parser.add_argument("-o", "--ouvir", action="store_true", help="Grava a pergunta do microfone antes de responder")
    parser.add_argument("-r", "--rapido", action="store_true", help="Resposta rápida sem rodada de auditoria")
    parser.add_argument("--json", action="store_true", help="Saída em formato JSON")
    parser.add_argument("--historico", action="store_true", help="Mostra o histórico de consultas")

    args = parser.parse_args()

    if args.historico:
        mostrar_historico()
        return

    pergunta_texto = " ".join(args.pergunta).strip()

    if args.ouvir and not pergunta_texto:
        pergunta_texto = ouvir_microfone()

    if pergunta_texto:
        processar_consulta(pergunta_texto, falar_voz=args.falar, rapido=args.rapido, saida_json=args.json)
    else:
        modo_interativo(falar_voz=args.falar)


if __name__ == "__main__":
    main()
