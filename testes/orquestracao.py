#!/usr/bin/env python3
"""Verifica persistência, dependências, reservas e revisão dos artefatos."""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('estado', RAIZ / 'default/orquestracao/estado.py')
MODULO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULO)


def tarefa(identificador='T1', **campos):
    return {'id': identificador, 'pedido': 'Leia a fonte', 'papel': 'leitor',
            'capacidade': 'leitura_documental', 'risco': 1, 'qualidade': 'medium',
            'fontes': ['fonte.md'], **campos}


class Persistencia(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = pathlib.Path(self.tmp.name) / 'estado'
        self.estado = MODULO.Estado(self.pasta)
        self.addCleanup(lambda: self.estado.fechar())

    def test_importacao_idempotente_sem_apagar_execucao(self):
        self.estado.importar([tarefa()])
        _, dono = self.estado.reservar()
        self.estado.finalizar('T1', dono, 'REVIEW_REQUIRED', {'gate': 'PASS'}, 'relatório')
        self.estado.revisar('T1', 'conferido na fonte', True)
        self.estado.importar([tarefa()])
        self.assertEqual(self.estado.listar()[0]['status'], 'COMPLETED')
        self.assertIsNone(self.estado.reservar())
        with self.assertRaises(ValueError):
            self.estado.importar([tarefa(pedido='Pedido alterado')])

    def test_dag_importacao_atomica(self):
        for plano in (
            [tarefa(dependencias=['T2'])],
            [tarefa(dependencias=['T2']), tarefa('T2', dependencias=['T1'])],
            [tarefa(), tarefa()],
        ):
            with self.subTest(plano=plano), self.assertRaises(ValueError):
                self.estado.importar(plano)
            self.assertEqual(self.estado.listar(), [])

    def test_dependencia_exige_revisao(self):
        self.estado.importar([tarefa(), tarefa('T2', dependencias=['T1'])])
        _, dono = self.estado.reservar()
        self.estado.finalizar('T1', dono, 'REVIEW_REQUIRED', {'gate': 'PASS'}, 'relatório')
        self.assertIsNone(self.estado.reservar())
        self.estado.revisar('T1', 'fiel à fonte', True)
        self.assertEqual(self.estado.reservar()[0]['id'], 'T2')

    def test_artefato_adulterado_nao_aprova(self):
        self.estado.importar([tarefa()])
        _, dono = self.estado.reservar()
        self.estado.finalizar('T1', dono, 'REVIEW_REQUIRED', {}, 'relatório')
        resumo = self.estado.listar()[0]
        (self.pasta / 'artefatos' / f'{resumo["artefato"]}.txt').write_text('alterado')
        with self.assertRaises(ValueError):
            self.estado.revisar('T1', 'aprovado', True)
        self.assertEqual(self.estado.listar()[0]['status'], 'REVIEW_REQUIRED')

    def test_reserva_expirada_exige_conferencia(self):
        self.estado.importar([tarefa()])
        with patch.object(MODULO.time, 'time', return_value=100):
            _, dono = self.estado.reservar(10)
        with patch.object(MODULO.time, 'time', return_value=111):
            self.assertIsNone(self.estado.reservar())
            with self.assertRaises(ValueError):
                self.estado.finalizar('T1', dono, 'REVIEW_REQUIRED', {}, 'relatório')
        self.assertEqual(self.estado.listar()[0]['status'], 'REVISION_REQUIRED')

    def test_reserva_de_outro_executor_nao_finaliza(self):
        self.estado.importar([tarefa()])
        self.estado.reservar()
        with self.assertRaises(ValueError):
            self.estado.finalizar('T1', 'outro', 'REVIEW_REQUIRED', {}, 'relatório')
        with self.assertRaises(ValueError):
            self.estado.finalizar('T1', 'outro', 'COMPLETED', {}, 'relatório')

    def test_reinicio_preserva_resultado_e_dependencia(self):
        self.estado.importar([tarefa(), tarefa('T2', dependencias=['T1'])])
        _, dono = self.estado.reservar()
        self.estado.finalizar('T1', dono, 'WAITING_QUOTA', {'motivo': 'cota esgotada'})
        outra = MODULO.Estado(self.pasta)
        self.addCleanup(outra.fechar)
        self.assertEqual(outra.listar()[0]['status'], 'WAITING_QUOTA')
        self.assertIsNone(outra.reservar())
        outra.alterar('T1', 'retomar')
        self.assertEqual(outra.reservar()[0]['id'], 'T1')

    def test_limite_de_tentativas(self):
        self.estado.importar([tarefa(max_tentativas=1)])
        _, dono = self.estado.reservar()
        self.estado.finalizar('T1', dono, 'REVISION_REQUIRED', {'motivo': 'falha'})
        self.estado.alterar('T1', 'repetir')
        self.assertIsNone(self.estado.reservar())
        self.assertEqual(self.estado.listar()[0]['status'], 'FAILED')

    def test_cancelamento_e_pausa(self):
        self.estado.importar([tarefa(), tarefa('T2')])
        self.estado.alterar('T1', 'pausar')
        self.estado.alterar('T2', 'cancelar')
        self.assertIsNone(self.estado.reservar())
        self.estado.alterar('T1', 'retomar')
        self.assertEqual(self.estado.reservar()[0]['id'], 'T1')
        with self.assertRaises(ValueError):
            self.estado.alterar('T2', 'retomar')

    def test_dois_executores_nao_reservam_a_mesma_tarefa(self):
        self.estado.importar([tarefa()])
        resultados = []
        barreira = threading.Barrier(2)

        def reservar():
            outro = MODULO.Estado(self.pasta)
            try:
                barreira.wait()
                resultados.append(outro.reservar())
            finally:
                outro.fechar()

        threads = [threading.Thread(target=reservar) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(resultados), 2)
        self.assertEqual(sum(resultado is not None for resultado in resultados), 1)

    def test_entrada_invalida_nao_cria_tarefas(self):
        for alteracao in ({'risco': True}, {'fontes': []}, {'qualidade': 'unknown'},
                          {'max_tentativas': 0}, {'dependencias': ['T1']},
                          {'permitir_remoto': 'true'}, {'requisitos': ['-opcao']}):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                self.estado.importar([tarefa(**alteracao)])
        self.assertEqual(self.estado.listar(), [])

    def test_estado_por_link_simbolico_recusado(self):
        link = pathlib.Path(self.tmp.name) / 'link'
        link.symlink_to(self.pasta, target_is_directory=True)
        with self.assertRaises(ValueError):
            MODULO.Estado(link)
        with self.assertRaises(ValueError):
            MODULO.Estado(link / 'subpasta')

    def test_identificador_de_artefato_nao_e_caminho(self):
        with self.assertRaises(ValueError):
            self.estado.ler_artefato('../../segredo')
        externo = pathlib.Path(self.tmp.name) / 'externo'
        externo.mkdir()
        (self.pasta / 'artefatos').symlink_to(externo, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.estado.ler_artefato('0' * 64)

    def test_comandos_importam_sem_executar_dados(self):
        projeto = pathlib.Path(self.tmp.name) / 'projeto'
        projeto.mkdir()
        (projeto / 'fonte.md').write_text('conteúdo de teste')
        (projeto / 'plano.json').write_text(json.dumps([tarefa(comando='touch invasao')]))
        ambiente = os.environ.copy()
        ambiente.update(JANGADA_PATH=str(RAIZ), XDG_STATE_HOME=str(pathlib.Path(self.tmp.name) / 'state'),
                        XDG_CONFIG_HOME=str(pathlib.Path(self.tmp.name) / 'config'))

        def executar(comando, *args):
            return subprocess.run([str(RAIZ / 'bin' / comando), *args], cwd=projeto,
                                  env=ambiente, capture_output=True, text=True, timeout=30)

        resultado = executar('jangada-fila', '--importar', 'plano.json', '--json')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        fila = json.loads(resultado.stdout)
        self.assertEqual(fila['tarefas'][0]['status'], 'QUEUED')
        self.assertFalse((projeto / 'invasao').exists())
        self.assertEqual(executar('jangada-task', 'T1', 'pausar').returncode, 0)
        self.assertEqual(json.loads(executar('jangada-fila', '--json').stdout)['tarefas'][0]['status'], 'PAUSED')
        self.assertEqual(executar('jangada-task', 'T1', 'retomar').returncode, 0)
        self.assertEqual(executar('jangada-task', 'T1', 'revisar', '--aprovar').returncode, 2)

    def test_cli_recusa_fontes_fora_do_projeto(self):
        projeto = pathlib.Path(self.tmp.name) / 'projeto'
        projeto.mkdir()
        segredo = pathlib.Path(self.tmp.name) / 'segredo.txt'
        segredo.write_text('não enviar')
        (projeto / 'plano.json').write_text(json.dumps([tarefa(fontes=['../segredo.txt'])]))
        ambiente = os.environ.copy()
        ambiente.update(JANGADA_PATH=str(RAIZ), XDG_STATE_HOME=str(pathlib.Path(self.tmp.name) / 'state'),
                        XDG_CONFIG_HOME=str(pathlib.Path(self.tmp.name) / 'config'))
        resultado = subprocess.run([str(RAIZ / 'bin/jangada-fila'), '--importar', 'plano.json'],
                                   cwd=projeto, env=ambiente, capture_output=True, text=True, timeout=30)
        self.assertEqual(resultado.returncode, 2)
        self.assertIn('fora do projeto', resultado.stderr)


if __name__ == '__main__':
    unittest.main()
