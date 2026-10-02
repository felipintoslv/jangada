"""Executa leitura delimitada e preserva saídas sem aprová-las."""

import contextlib
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import signal
import subprocess
import tempfile
import time

CAPACIDADES = {'leitura_documental', 'resumo_curto', 'analise_documental'}
PERFIS = {'balanced', 'quality', 'offline'}


def chamadas(registro, codigo_saida):
    tentativas = registro.get('tentativas')
    if (tentativas == [] and codigo_saida == 4 and registro.get('recusa') is True
            and type(registro.get('chamadas_executor')) is int and registro['chamadas_executor'] == 0
            and registro.get('motivo_codigo') in {'destino_proibido', 'capacidade_incompativel',
                                                'fonte_ausente', 'politica_invalida', 'sem_executor'}):
        return 0
    if not isinstance(tentativas, list) or not tentativas:
        return None
    valores = [item.get('chamadas') for item in tentativas if isinstance(item, dict)]
    if len(valores) != len(tentativas) or any(type(v) is not int or v < 0 for v in valores):
        return None
    return sum(valores)


def conferir_fontes(tarefa, projeto):
    for nome in tarefa['fontes']:
        fonte = pathlib.Path(nome)
        if not fonte.resolve().is_relative_to(projeto) or not fonte.is_file():
            raise ValueError(f'fonte ausente ou fora do projeto: {nome}')
        if hashlib.sha256(fonte.read_bytes()).hexdigest() != tarefa.get('hashes_fontes', {}).get(nome):
            raise ValueError(f'fonte alterada após importação: {nome}')


def executar_uma(estado, projeto, raiz, perfil, permitir_remoto):
    reserva = estado.reservar()
    if reserva is None:
        return None
    tarefa, dono = reserva
    identificador = tarefa['id']
    consumo = estado.consumo(identificador)
    resultado = {'perfil': perfil, 'execucao_iniciada': False,
                 'metricas': {'chamadas': 0, 'segundos': 0}}
    texto = None

    def encerrar(status, motivo, artefato=None):
        resultado['motivo'] = motivo
        estado.finalizar(identificador, dono, status, resultado, artefato)
        return {'tarefa': identificador, 'status': status, **resultado}

    if tarefa['papel'] != 'leitor' or tarefa['capacidade'] not in CAPACIDADES:
        return encerrar('WAITING_PROVIDER', 'capacidade ainda sem adaptador de execução')
    if tarefa['risco'] > 2 or tarefa['qualidade'] in {'high', 'critical'}:
        return encerrar('WAITING_REVIEWER', 'tarefa exige executor principal ainda não integrado')
    if consumo['chamadas'] is None:
        return encerrar('REVISION_REQUIRED', 'consumo anterior desconhecido; não repetir automaticamente')
    saldo = tarefa.get('max_chamadas', 8) - consumo['chamadas']
    tempo = tarefa.get('tempo_total', 600) - consumo['segundos']
    if saldo <= 0 or tempo <= 0:
        return encerrar('FAILED', 'orçamento total da tarefa esgotado')
    try:
        conferir_fontes(tarefa, projeto)
        fontes = list(tarefa['fontes'])
        mapa = {item['id']: item for item in estado.listar()}
        for dependencia in tarefa.get('dependencias', []):
            resumo = mapa[dependencia]['artefato']
            estado.ler_artefato(resumo)
            fontes.append(str(estado.pasta / 'artefatos' / f'{resumo}.txt'))
        # A reserva cobre o prazo real e a persistência, sem repetir um executor ainda ativo.
        with estado.transacao():
            estado.db.execute('UPDATE tarefas SET prazo=? WHERE id=? AND dono=?',
                              (time.time() + tempo + 60, identificador, dono))
        argumentos = [str(raiz / 'bin/jangada-delegar'), '--json', '--capacidade', tarefa['capacidade']]
        if perfil == 'offline':
            argumentos += ['--destino', 'local']
        elif perfil == 'quality':
            argumentos += ['--destino', 'agy']
        if permitir_remoto and tarefa.get('permitir_remoto', False) and perfil != 'offline':
            argumentos.append('--permitir-remoto')
        for requisito in tarefa.get('requisitos', []):
            argumentos += ['--requisito', requisito]
        argumentos += ['--arquivos', *fontes]
        argumentos += ['--', tarefa['papel'], tarefa['pedido']]
        ambiente = os.environ.copy()
        for chave in ('JANGADA_DELEGAR_ROTEAMENTO_ID', 'JANGADA_DELEGAR_TENTATIVAS',
                      'JANGADA_DELEGAR_CHAMADAS_RESTANTES', 'JANGADA_DELEGAR_DECISAO',
                      'JANGADA_DELEGAR_CACHE_PREFIXO'):
            ambiente.pop(chave, None)
        ambiente.update(JANGADA_PATH=str(raiz), JANGADA_DELEGAR_TEMPO_TOTAL=str(tempo),
                        JANGADA_DELEGAR_CHAMADAS_MAX=str(saldo))
        with tempfile.TemporaryDirectory(prefix='execucao-', dir=estado.pasta) as pasta:
            saida = pathlib.Path(pasta) / 'relatorio.md'
            argumentos[1:1] = ['--arquivo', str(saida)]
            inicio = time.monotonic()
            processo = subprocess.Popen(argumentos, cwd=projeto, env=ambiente,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8', start_new_session=True)
            resultado['execucao_iniciada'] = True
            resultado['metricas']['chamadas'] = None
            try:
                bruto, erro = processo.communicate(timeout=tempo)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as interrupcao:
                resultado['metricas'] = {'chamadas': None, 'segundos': math.ceil(time.monotonic() - inicio)}
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(processo.pid, signal.SIGKILL)
                processo.communicate()
                encerramento = encerrar('REVISION_REQUIRED', 'executor interrompido; consumo de chamadas desconhecido')
                if isinstance(interrupcao, KeyboardInterrupt):
                    raise
                return encerramento
            except (OSError, UnicodeError):
                resultado['metricas'] = {'chamadas': None, 'segundos': math.ceil(time.monotonic() - inicio)}
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(processo.pid, signal.SIGKILL)
                processo.wait()
                raise
            resultado['metricas'] = {'chamadas': None, 'segundos': math.ceil(time.monotonic() - inicio)}
            resultado['erro'] = erro[-4000:]
            registro = json.loads(bruto)
            if not isinstance(registro, dict):
                raise ValueError('executor não devolveu objeto estruturado')
            quantidade = chamadas(registro, processo.returncode)
            resultado['metricas']['chamadas'] = quantidade
            resultado['execucao_iniciada'] = quantidade != 0
            resultado['delegacao'] = registro
            if quantidade is None or quantidade > saldo:
                return encerrar('REVISION_REQUIRED', 'executor não comprovou respeito ao orçamento')
            if processo.returncode != 0:
                motivos = {registro.get('motivo_codigo')}
                motivos.update(t.get('motivo_codigo') for t in registro.get('tentativas', []) if isinstance(t, dict))
                if motivos & {'cota_insuficiente', 'cota_desconhecida'}:
                    return encerrar('WAITING_QUOTA', 'cota insuficiente ou desconhecida')
                if 'saida_invalida' in motivos:
                    return encerrar('REVISION_REQUIRED', 'saída reprovada na conferência')
                return encerrar('WAITING_PROVIDER', 'nenhum executor elegível concluiu a tarefa')
            if not saida.is_file() or saida.is_symlink() or saida.stat().st_size > 10 * 1024 * 1024:
                raise ValueError('executor não produziu relatório completo dentro do limite de tamanho')
            texto = saida.read_text(encoding='utf-8')
            if not texto.strip():
                raise ValueError('relatório vazio')
            conferir_fontes(tarefa, projeto)
            for dependencia in tarefa.get('dependencias', []):
                estado.ler_artefato(mapa[dependencia]['artefato'])
            spec = importlib.util.spec_from_file_location('validar_delegacao', raiz / 'default/delegacao/validar.py')
            verificador = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verificador)
            verificador.verificar(texto, fontes, tarefa.get('requisitos', []))
            resultado['verificacao'] = 'referencias_e_requisitos_validos'
            return encerrar('REVIEW_REQUIRED', 'formato conferido; conteúdo aguarda revisão', texto)
    except (OSError, UnicodeError, ValueError, KeyError, subprocess.SubprocessError) as erro:
        return encerrar('REVISION_REQUIRED', str(erro), texto)


def executar(estado, projeto, raiz, perfil='balanced', limite=1, permitir_remoto=False):
    if perfil not in PERFIS or type(limite) is not int or not 1 <= limite <= 1000:
        raise ValueError('perfil ou limite de tarefas inválido')
    resultados = []
    for _ in range(limite):
        resultado = executar_uma(estado, projeto, raiz, perfil, permitir_remoto)
        if resultado is None:
            break
        resultados.append(resultado)
    return resultados
