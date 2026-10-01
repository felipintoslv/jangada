#!/usr/bin/env python3
"""Fontes artificiais, sem chamadas a provedores ou leitura de credenciais."""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('metricas', Path(__file__).resolve().parents[1] / 'default/painel/metricas.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
AGORA = dt.datetime(2026, 9, 30, 23, 4, 50, tzinfo=dt.timezone(dt.timedelta(hours=-3)))


def evento(tipo, payload, quando='2026-10-01T01:00:00Z'):
    return {'timestamp': quando, 'type': tipo, 'payload': payload}


class Metricas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.estado = self.raiz / 'estado'
        self.codex = self.raiz / 'codex'
        self.cache = self.raiz / 'cache'
        self.cache.mkdir(); self.estado.mkdir()
        self.env = patch.dict(os.environ, JANGADA_ESTADO=str(self.estado), CODEX_HOME=str(self.codex))
        self.env.start(); self.addCleanup(self.env.stop)

    def gravar(self, caminho, registros, resto=''):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(''.join(json.dumps(d) + '\n' for d in registros) + resto)

    def coletar(self):
        return m.coletar(self.cache, AGORA)

    def test_respostas_deduplicadas_e_dia_local(self):
        r = evento('token_usage_record', {'response_id': 'r1', 'usage': {'input_tokens': 100, 'output_tokens': 5}})
        self.gravar(self.codex / 'sessions/rollout-a.jsonl', [r, r, evento('event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 100}}})])
        cs, _, _ = self.coletar()
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]['entrada_total'], 100)
        self.assertEqual(cs[0]['dia'], '2026-09-30')
        self.assertEqual(cs[0]['origem'], 'interface_externa')
        self.assertIsNone(cs[0]['cache_lido'])

    def test_cumulativos_repetidos_nao_somam(self):
        rs = [evento('event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': n, 'output_tokens': 0}}}, f'2026-10-01T01:00:0{i}Z') for i, n in enumerate([10, 10, 25])]
        self.gravar(self.estado / 'codex/sessions/rollout-a.jsonl', rs)
        cs, _, _ = self.coletar()
        self.assertEqual(sum(c['entrada_total'] for c in cs), 25)
        self.assertTrue(all(c['origem'] == 'jangada' for c in cs))

    def test_registro_invalido_nao_inibe_formato_cumulativo(self):
        rs = [evento('token_usage_record', {'response_id': '', 'usage': {}}),
              evento('event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 12}}})]
        self.gravar(self.codex / 'sessions/rollout-a.jsonl', rs)
        cs, _, _ = self.coletar()
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]['entrada_total'], 12)

    def test_linha_parcial_e_ferramenta_sem_argumentos(self):
        rs = [evento('response_item', {'type': 'function_call', 'call_id': 'a', 'name': 'exec', 'arguments': 'SEGREDO'}), evento('response_item', {'type': 'function_call_output', 'call_id': 'a', 'output': 'SEGREDO'})]
        self.gravar(self.codex / 'sessions/rollout-a.jsonl', rs, '{"type":')
        _, fs, _ = self.coletar()
        self.assertEqual(fs[0]['resultado'], 'registrado')
        self.assertNotIn('SEGREDO', repr(fs))

    def test_codex_incremental_preserva_contexto_e_resultados(self):
        caminho = self.codex / 'sessions/rollout-a.jsonl'
        self.gravar(caminho, [evento('session_meta', {'id': 'sessao', 'cwd': '/projeto'}),
            evento('turn_context', {'model': 'modelo'}),
            evento('token_usage_record', {'response_id': 'r1', 'usage': {'input_tokens': 10}}),
            evento('response_item', {'type': 'function_call', 'call_id': 'a', 'name': 'exec',
                                    'arguments': 'SEGREDO'})])
        cs, fs, cobertura = self.coletar()
        primeira = next(c for c in cobertura if c['fonte'] == 'codex_externo')
        self.assertEqual(primeira['bytes_lidos'], caminho.stat().st_size)
        self.assertEqual(fs[0]['resultado'], 'sem_resultado')
        self.assertEqual(self.coletar()[:2], (cs, fs))
        segunda = next(c for c in self.coletar()[2] if c['fonte'] == 'codex_externo')
        self.assertEqual(segunda['bytes_lidos'], 0)
        self.assertEqual(segunda['arquivos_lidos'], 0)
        novos = [evento('token_usage_record', {'response_id': 'r2', 'usage': {'input_tokens': 5}}),
                 evento('response_item', {'type': 'function_call_output', 'call_id': 'a', 'output': 'SEGREDO'})]
        acrescentado = ''.join(json.dumps(d) + '\n' for d in novos)
        with caminho.open('a') as arq:
            arq.write(acrescentado)
        cs, fs, cobertura = self.coletar()
        self.assertEqual(sum(c['entrada_total'] for c in cs), 15)
        self.assertEqual(cs[1]['modelo'], 'modelo')
        self.assertEqual(cs[1]['sessao'], 'sessao')
        self.assertEqual(fs[0]['resultado'], 'registrado')
        self.assertEqual(next(c for c in cobertura if c['fonte'] == 'codex_externo')['bytes_lidos'],
                         len(acrescentado.encode()))
        self.assertNotIn('SEGREDO', (self.cache / 'codex-interface_externa.json').read_text())

    def test_linha_parcial_completada_na_coleta_seguinte(self):
        caminho = self.codex / 'sessions/rollout-a.jsonl'
        registro = json.dumps(evento('token_usage_record', {'response_id': 'r1', 'usage': {'output_tokens': 2}}))
        self.gravar(caminho, [], registro[:20])
        self.assertFalse(self.coletar()[0])
        with caminho.open('a') as arq:
            arq.write(registro[20:] + '\n')
        self.assertEqual(self.coletar()[0][0]['saida'], 2)
        self.assertEqual(len(self.coletar()[0]), 1)

    def test_cumulativos_incrementais_substituidos_por_respostas(self):
        caminho = self.codex / 'sessions/rollout-a.jsonl'
        self.gravar(caminho, [evento('event_msg', {'type': 'token_count',
            'info': {'total_token_usage': {'input_tokens': 10}}})])
        self.assertEqual(self.coletar()[0][0]['entrada_total'], 10)
        with caminho.open('a') as arq:
            arq.write(json.dumps(evento('event_msg', {'type': 'token_count',
                'info': {'total_token_usage': {'input_tokens': 25}}}, '2026-10-01T01:00:01Z')) + '\n')
        self.assertEqual(sum(c['entrada_total'] for c in self.coletar()[0]), 25)
        with caminho.open('a') as arq:
            arq.write(json.dumps(evento('token_usage_record', {'response_id': 'r1',
                'usage': {'input_tokens': 25}})) + '\n')
        cs = self.coletar()[0]
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]['id'], 'codex:r1')

    def test_truncamento_rotacao_e_reescrita(self):
        caminho = self.codex / 'sessions/rollout-a.jsonl'
        r1 = evento('token_usage_record', {'response_id': 'r1', 'usage': {'input_tokens': 10}})
        r2 = evento('token_usage_record', {'response_id': 'r2', 'usage': {'input_tokens': 20}})
        self.gravar(caminho, [r1, r1])
        self.coletar()
        self.gravar(caminho, [r2])
        self.assertEqual(self.coletar()[0][0]['entrada_total'], 20)
        self.gravar(caminho, [r1])
        self.assertEqual(self.coletar()[0][0]['entrada_total'], 10)
        os.replace(caminho, caminho.with_suffix('.anterior'))
        self.gravar(caminho, [r2])
        self.assertEqual(self.coletar()[0][0]['entrada_total'], 20)

    def test_falha_nao_avanca_memo_e_cache_invalido_reconstroi(self):
        caminho = self.codex / 'sessions/rollout-a.jsonl'
        self.gravar(caminho, [evento('token_usage_record', {'response_id': 'r1', 'usage': {'input_tokens': 3}})])
        self.coletar()
        memo = self.cache / 'codex-interface_externa.json'
        antes = memo.read_bytes()
        with caminho.open('a') as arq:
            arq.write('invalido\n')
        cobertura = next(c for c in self.coletar()[2] if c['fonte'] == 'codex_externo')
        self.assertEqual(cobertura['estado'], 'erro')
        self.assertEqual(memo.read_bytes(), antes)
        self.gravar(caminho, [evento('token_usage_record', {'response_id': 'r2', 'usage': {'input_tokens': 7}})])
        memo.write_text('{invalido')
        self.assertEqual(self.coletar()[0][0]['entrada_total'], 7)

    def test_chamadas_local_substituem_agregado_inclusive_parciais(self):
        d = dict(data='2026-09-30T22:00:00-03:00', destino='local', delegacao_id='d1', recusa=True,
                 tokens_local_entrada=9999, chamadas_local=[dict(id='c1', tokens_entrada=12, tokens_saida=0, tempos_ms={'geracao': 10})])
        self.gravar(self.estado / 'delegacoes.jsonl', [d, d])
        cs, _, _ = self.coletar()
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]['entrada_total'], 12)
        self.assertEqual(cs[0]['saida'], 0)
        self.assertEqual(cs[0]['tempo_geracao_ms'], 10)
        self.assertEqual(cs[0]['estado'], 'parcial')

    def test_legados_iguais_preservam_duas_ocorrencias(self):
        d = dict(data='2026-09-30T22:00:00-03:00', destino='local', tokens_local_entrada=5, tokens_local_saida=0)
        self.gravar(self.estado / 'delegacoes.jsonl', [d, d])
        cs, _, _ = self.coletar()
        self.assertEqual(len(cs), 2)
        self.assertEqual(cs, self.coletar()[0])

    def test_numeros_invalidos_e_zero(self):
        for v in [None, True, False, -1, float('nan'), float('inf'), '3']:
            self.assertIsNone(m.numero(v))
        self.assertEqual(m.numero(0), 0)

    def test_falha_fonte_independente_e_nao_segue_link(self):
        alvo = self.raiz / 'dados.jsonl'
        self.gravar(alvo, [evento('token_usage_record', {'response_id': 'r', 'usage': {'input_tokens': 5}})])
        pasta = self.codex / 'sessions'; pasta.mkdir(parents=True)
        (pasta / 'rollout-link.jsonl').symlink_to(alvo)
        self.gravar(self.estado / 'delegacoes.jsonl', [dict(data='2026-09-30T22:00:00-03:00', destino='local', tokens_local_saida=3)])
        cs, _, cob = self.coletar()
        self.assertEqual(len(cs), 1)
        self.assertEqual(next(c for c in cob if c['fonte'] == 'codex_externo')['estado'], 'erro')

    def test_fonte_com_erro_preserva_data_contagens_e_metricas(self):
        try:
            import pyarrow
        except ImportError:
            self.skipTest('pyarrow ausente')
        pasta = Path(__file__).resolve().parents[1] / 'default/painel'
        with patch.object(sys, 'path', [str(pasta)] + sys.path):
            spec = importlib.util.spec_from_file_location('coletor_teste', pasta / 'coletor.py')
            coletor = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(coletor)
            caminho = self.codex / 'sessions/rollout-a.jsonl'
            self.gravar(caminho, [evento('token_usage_record', {'response_id': 'r1',
                'usage': {'input_tokens': 8}})])
            cs, cobertura = coletor.metricas_unificadas(str(self.cache), AGORA)
            fonte = next(c for c in cobertura if c['fonte'] == 'codex_externo')
            with caminho.open('a') as arq:
                arq.write('invalido\n')
            depois = AGORA + dt.timedelta(hours=1)
            cs2, cobertura2 = coletor.metricas_unificadas(str(self.cache), depois)
            fonte2 = next(c for c in cobertura2 if c['fonte'] == 'codex_externo')
            self.assertEqual(fonte2['estado'], 'erro')
            self.assertEqual(fonte2['atualizado'], fonte['atualizado'])
            self.assertEqual(fonte2['ultima_tentativa'], depois.isoformat())
            self.assertEqual(fonte2['registros'], 1)
            self.assertTrue(fonte2['dados_preservados'])
            self.assertEqual(cs, cs2)
            self.gravar(caminho, [evento('token_usage_record', {'response_id': 'r1',
                'usage': {'input_tokens': 8}}), evento('token_usage_record', {'response_id': 'r2',
                'usage': {'input_tokens': 5}})])
            with patch.object(coletor, 'gravar_tabela', side_effect=OSError('publicação interrompida')):
                preservado, _ = coletor.metricas_unificadas(str(self.cache), depois)
            self.assertEqual(preservado, cs)
            recuperado, _ = coletor.metricas_unificadas(str(self.cache), depois)
            self.assertEqual(sum(c['entrada_total'] for c in recuperado), 13)

    def test_claude_soma_entrada_cache_sem_inventar_origem(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest('pyarrow ausente')
        pasta = self.cache / 'mensagens'; pasta.mkdir()
        pq.write_table(pa.Table.from_pylist([dict(id='m1', data=AGORA, entrada=2, cache_lido=3, cache_criado=4, saida=1, modelo='claude')]), pasta / 'a.parquet')
        cs, _, _ = self.coletar()
        self.assertEqual(cs[0]['entrada_total'], 9)
        self.assertEqual(cs[0]['origem'], 'historico_claude')

    def test_ferramentas_claude_dedup_resultado_sem_conteudo(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest('pyarrow ausente')
        for nome in ('ferramentas', 'resultados'):
            (self.cache / nome).mkdir()
        chamadas = [dict(id=i, data=AGORA, sessao='agente' if i == 'a' else '', ferramenta='Bash', alvo='SEGREDO') for i in ('a', 'b', 'c')]
        for nome in ('a', 'b'):
            pq.write_table(pa.Table.from_pylist(chamadas), self.cache / 'ferramentas' / (nome + '.parquet'))
        pq.write_table(pa.Table.from_pylist([dict(id='a', erro=True), dict(id='b', erro=False)]), self.cache / 'resultados/a.parquet')
        _, fs, _ = self.coletar()
        self.assertEqual(len(fs), 3)
        self.assertEqual([f['resultado'] for f in fs], ['erro', 'registrado', 'sem_resultado'])
        self.assertEqual(fs[0]['origem'], 'jangada')
        self.assertEqual(fs[1]['origem'], 'historico_claude')
        self.assertNotIn('SEGREDO', repr(fs))


if __name__ == '__main__':
    unittest.main()
