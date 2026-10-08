"""Retratos somente de leitura e recortes de autonomia sobre registros sintéticos."""

import datetime as dt
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'default/painel'))
import autonomia
import orquestracao


class Painel(unittest.TestCase):
    def test_retrato_sem_iniciar_execucao_e_com_consumo_desconhecido(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            projeto = raiz / 'projeto'
            chave = hashlib.sha256(str(projeto).encode()).hexdigest()
            estado = orquestracao.Estado(raiz / 'agentes/projetos' / chave, raiz=raiz)
            spec = dict(id='leitura', pedido='Leia', papel='leitor', capacidade='leitura_documental',
                        risco=1, qualidade='low', fontes=['doc.txt'], max_chamadas=4, tempo_total=120)
            estado.importar([spec, dict(spec, id='dependente', dependencias=['leitura'])])
            estado.db.execute("UPDATE tarefas SET status='WAITING_QUOTA',motivo='cota baixa' WHERE id='leitura'")
            estado.evento('leitura', 'execucao_encerrada', {'resultado': {'metricas': {'chamadas': None}}})
            runtime = orquestracao.Estado(raiz / 'agentes/runtime', raiz=raiz)
            saude = orquestracao.Saude(runtime)
            saude.observar('codex', 'AVAILABLE', 'observado', validade=1, cota=80)
            runtime.db.execute("UPDATE provedores SET valido_ate=1 WHERE id='codex'")
            bancos = [estado, runtime]
            estado.db.execute('PRAGMA wal_autocheckpoint=0')
            estado.db.execute('BEGIN IMMEDIATE')
            estado.db.execute("UPDATE tarefas SET status='FAILED' WHERE id='leitura'")
            arquivos_antes = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                              for p in raiz.rglob('*') if p.is_file()}
            antes = [e.db.total_changes for e in bancos]
            with patch.object(orquestracao.Estado, '__init__', side_effect=AssertionError('escrita')), \
                    patch.object(orquestracao.Saude, '__init__', side_effect=AssertionError('consulta remota')), \
                    patch.dict(os.environ, JANGADA_CONFIG=str(raiz / 'config')):
                retrato = orquestracao.coletar(raiz, [projeto], lambda p: Path(p).name)
            self.assertEqual(retrato['erros'], [])
            tarefa = next(t for t in retrato['tarefas'] if t['id'] == 'leitura')
            self.assertIsNone(tarefa['saldo_chamadas'])
            self.assertIsNone(tarefa['saldo_segundos'])
            self.assertEqual(tarefa['motivo'], 'cota baixa')
            dependente = next(t for t in retrato['tarefas'] if t['id'] == 'dependente')
            self.assertEqual(dependente['dependencias'], 'leitura')
            self.assertEqual(dependente['saldo_chamadas'], 4)
            self.assertIsNone(retrato['projetos'][0]['custo_estimado'])
            codex = next(p for p in retrato['provedores'] if p['id'] == 'codex')
            self.assertEqual(codex['status'], 'UNKNOWN')
            self.assertIsNone(codex['cota'])
            self.assertEqual([e.db.total_changes for e in bancos], antes)
            self.assertEqual(arquivos_antes, {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                                             for p in raiz.rglob('*') if p.is_file()})
            estado.db.execute('ROLLBACK')
            consulta = orquestracao.Consulta(estado.pasta / 'tarefas.sqlite')
            with self.assertRaises(sqlite3.OperationalError):
                consulta.db.execute('DELETE FROM tarefas')
            consulta.fechar()
            for e in bancos:
                e.fechar()

    def test_ausencia_e_banco_corrompido_nao_criam_estado(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            self.assertEqual(orquestracao.coletar(raiz, [], str)['tarefas'], [])
            self.assertFalse((raiz / 'agentes').exists())
            banco = raiz / 'agentes/projetos/corrompido/tarefas.sqlite'
            banco.parent.mkdir(parents=True)
            banco.write_text('não é sqlite', encoding='utf-8')
            resultado = orquestracao.coletar(raiz, [], str)
            self.assertEqual(resultado['tarefas'], [])
            self.assertEqual(len(resultado['erros']), 1)
            self.assertEqual(banco.read_text(encoding='utf-8'), 'não é sqlite')

    def test_autonomia_filtra_antes_de_calcular_mediana_e_destinos(self):
        hoje = dt.datetime.now().astimezone()
        ontem = hoje - dt.timedelta(days=1)
        registros = dict(subagentes=[], entregas=[], delegacoes=[
            dict(data=hoje.isoformat(), projeto='a', destino='codex-economico', sem_fonte=2),
            dict(data=hoje.isoformat(), projeto='b', destino='local', sem_fonte=9),
            dict(data=ontem.isoformat(), projeto='a', destino='codex-economico', sem_fonte=10)])
        pedido = dict(inicio=hoje.date().isoformat(), fim=hoje.date().isoformat(), projetos=['a'])
        resultado = autonomia.filtrar(dict(registros=registros), pedido)
        self.assertEqual(resultado['destinos'], {'codex-economico': 1})
        self.assertEqual(resultado['qualidade']['por_destino']['codex-economico']['mediana'], 2)
        pedido['inicio'] = ontem.date().isoformat()
        resultado = autonomia.filtrar(dict(registros=registros), pedido)
        self.assertEqual(resultado['qualidade']['por_destino']['codex-economico']['mediana'], 6)
        pedido['projetos'] = ['inexistente']
        self.assertEqual(autonomia.filtrar(dict(registros=registros), pedido)['destinos'], {})
        self.assertIn('erro', autonomia.filtrar({}, pedido))


if __name__ == '__main__':
    unittest.main()
