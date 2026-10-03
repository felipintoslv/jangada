"""Resume observações da fila, sem transformar registros em autorização."""

import collections
import json


def inteiro(valor):
    return type(valor) is int and valor >= 0


def identidade(resultado):
    registro = resultado.get('delegacao')
    registro = registro if isinstance(registro, dict) else {}
    executor = resultado.get('executor') or registro.get('destino')
    executor = executor if isinstance(executor, str) and executor else 'nao_informado'
    modelo = registro.get('modelo')
    modelo = modelo if isinstance(modelo, str) and modelo else None
    return executor, modelo


def grupo_executor(executores, executor, modelo):
    return executores.setdefault((executor, modelo), dict(executor=executor, modelo=modelo,
        execucoes_registradas=0, processamentos_confirmados=0, reservas_expiradas=0, reservas_em_aberto=0,
        chamadas_do_fluxo_confirmadas=0, chamadas_do_fluxo_desconhecidas=0,
        segundos_do_fluxo_confirmados=0, duracoes_do_fluxo_desconhecidas=0))


def resumir(estado):
    estado.db.execute('BEGIN')
    try:
        tarefas = {t['id']: t for t in estado.listar()}
        totais = dict(tarefas=len(tarefas), estados=dict(collections.Counter(t['status'] for t in tarefas.values())),
                      execucoes_registradas=0, processamentos_confirmados=0, recusas_sem_chamadas=0,
                      reservas_expiradas=0, reservas_em_aberto=0, repeticoes_solicitadas=0, retomadas=0,
                      chamadas=0, chamadas_confirmadas=0, chamadas_desconhecidas=0,
                      segundos=0, segundos_confirmados=0, duracoes_desconhecidas=0,
                      tokens_entrada=0, tokens_saida=0, tokens_entrada_confirmados=0,
                      tokens_saida_confirmados=0, mudancas_entre_candidatos=0,
                      revisoes_aprovadas=0, revisoes_reprovadas=0, revisoes_sem_saida=0,
                      custo_estimado=None)
        executores, janelas, saidas = {}, {}, {}
        eventos = estado.db.execute('SELECT tarefa,evento,dados FROM eventos ORDER BY seq')
        for evento in eventos:
            identificador = evento['tarefa']
            dados = json.loads(evento['dados'])
            tipo = evento['evento']
            if tipo == 'retomar':
                totais['retomadas'] += 1
            elif tipo == 'repetir':
                totais['repeticoes_solicitadas'] += 1
            elif tipo == 'reserva_expirada':
                totais['reservas_expiradas'] += 1
                totais['chamadas_desconhecidas'] += 1
                totais['duracoes_desconhecidas'] += 1
                grupo = grupo_executor(executores, 'nao_informado', None)
                grupo['reservas_expiradas'] += 1
                grupo['chamadas_do_fluxo_desconhecidas'] += 1
                grupo['duracoes_do_fluxo_desconhecidas'] += 1
                for campo in ('chamadas', 'segundos', 'tokens_entrada', 'tokens_saida'):
                    totais[campo] = None
                saidas.pop(identificador, None)
            elif tipo == 'execucao_encerrada':
                resultado = dados.get('resultado')
                resultado = resultado if isinstance(resultado, dict) else {}
                metricas = resultado.get('metricas')
                metricas = metricas if isinstance(metricas, dict) else {}
                quantidade, segundos = metricas.get('chamadas'), metricas.get('segundos')
                iniciou = resultado.get('execucao_iniciada') is True or inteiro(quantidade) and quantidade > 0
                totais['execucoes_registradas'] += 1
                totais['processamentos_confirmados'] += int(iniciou)
                totais['recusas_sem_chamadas'] += int(inteiro(quantidade) and quantidade == 0 and resultado.get('execucao_iniciada') is False)
                for campo, valor, desconhecido in (('chamadas', quantidade, 'chamadas_desconhecidas'),
                                                   ('segundos', segundos, 'duracoes_desconhecidas')):
                    if inteiro(valor):
                        totais[campo + '_confirmadas' if campo == 'chamadas' else campo + '_confirmados'] += valor
                        if totais[campo] is not None:
                            totais[campo] += valor
                    else:
                        totais[campo] = None
                        totais[desconhecido] += 1
                executor, modelo = identidade(resultado)
                grupo = grupo_executor(executores, executor, modelo)
                grupo['execucoes_registradas'] += 1
                grupo['processamentos_confirmados'] += int(iniciou)
                if inteiro(quantidade):
                    grupo['chamadas_do_fluxo_confirmadas'] += quantidade
                else:
                    grupo['chamadas_do_fluxo_desconhecidas'] += 1
                if inteiro(segundos):
                    grupo['segundos_do_fluxo_confirmados'] += segundos
                else:
                    grupo['duracoes_do_fluxo_desconhecidas'] += 1
                registro = resultado.get('delegacao')
                registro = registro if isinstance(registro, dict) else {}
                tentativas = registro.get('tentativas')
                tentativas = tentativas if isinstance(tentativas, list) else []
                if not inteiro(quantidade):
                    parcial = sum(t['chamadas'] for t in tentativas
                                  if isinstance(t, dict) and inteiro(t.get('chamadas')))
                    totais['chamadas_confirmadas'] += parcial
                    grupo['chamadas_do_fluxo_confirmadas'] += parcial
                destinos = [t.get('destino') for t in tentativas if isinstance(t, dict)
                            and isinstance(t.get('destino'), str) and t['destino']]
                totais['mudancas_entre_candidatos'] += sum(a != b for a, b in zip(destinos, destinos[1:]))
                for campo, origem in (('tokens_entrada', 'tokens_codex_entrada'), ('tokens_saida', 'tokens_codex_saida')):
                    valor = registro.get(origem)
                    if inteiro(valor):
                        totais[campo + '_confirmados'] += valor
                    completo = inteiro(quantidade) and (quantidade == 0 or (
                        quantidade == 1 and executor == 'codex-economico' and inteiro(valor)))
                    if not completo:
                        totais[campo] = None
                    elif totais[campo] is not None:
                        totais[campo] += valor if quantidade else 0
                saidas.pop(identificador, None)
                if dados.get('status') == 'REVIEW_REQUIRED' and dados.get('artefato'):
                    spec = tarefas[identificador]['especificacao']
                    saidas[identificador] = (spec['capacidade'], executor, modelo, spec['risco'])
            elif tipo == 'revisada':
                status = dados.get('status')
                if status not in {'COMPLETED', 'REVISION_REQUIRED'}:
                    continue
                aprovado = status == 'COMPLETED'
                totais['revisoes_aprovadas' if aprovado else 'revisoes_reprovadas'] += 1
                chave = saidas.pop(identificador, None)
                if chave is None:
                    totais['revisoes_sem_saida'] += 1
                else:
                    janelas.setdefault(chave, collections.deque(maxlen=50)).append(aprovado)
        abertas = sum(t['status'] == 'RUNNING' for t in tarefas.values())
        if abertas:
            totais['reservas_em_aberto'] = abertas
            totais['chamadas_desconhecidas'] += abertas
            totais['duracoes_desconhecidas'] += abertas
            for campo in ('chamadas', 'segundos', 'tokens_entrada', 'tokens_saida'):
                totais[campo] = None
            grupo = grupo_executor(executores, 'nao_informado', None)
            grupo['reservas_em_aberto'] += abertas
            grupo['chamadas_do_fluxo_desconhecidas'] += abertas
            grupo['duracoes_do_fluxo_desconhecidas'] += abertas
        desempenho = []
        for (capacidade, executor, modelo, risco), janela in sorted(janelas.items(), key=lambda item: str(item[0])):
            n = len(janela)
            erros = n - sum(janela)
            taxa = erros / n
            amostra = 1.0
            if n >= 20 and risco <= 1 and executor not in {'nao_informado', 'deterministico'} and modelo:
                amostra = 1.0 if taxa > 0.15 else (0.5 if taxa > 0.05 else 0.1)
            desempenho.append(dict(capacidade=capacidade, executor=executor, modelo=modelo, risco=risco,
                revisoes_na_janela=n, aprovadas=sum(janela), reprovadas=erros,
                taxa_reprovacao=taxa, amostragem_sugerida=amostra))
        return {**totais, 'por_executor': sorted(executores.values(), key=lambda item: str((item['executor'], item['modelo']))),
                'desempenho': desempenho}
    finally:
        estado.db.execute('ROLLBACK')
