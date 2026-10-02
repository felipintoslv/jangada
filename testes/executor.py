#!/usr/bin/env python3
"""Integra fila e executor simulado sem chamar modelos ou serviços externos."""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'default/orquestracao'))
from estado import Estado
from executor import executar

SIMULADO = '''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
args = sys.argv[1:]
pathlib.Path(os.environ['REGISTRO_TESTE']).write_text(json.dumps({'args': args, 'env': {
    nome: os.environ.get(nome) for nome in ['JANGADA_DELEGAR_TEMPO_TOTAL',
    'JANGADA_DELEGAR_CHAMADAS_MAX', 'JANGADA_DELEGAR', 'JANGADA_DELEGAR_ROTEAMENTO_ID']}}))
modo = os.environ.get('MODO_TESTE', 'ok')
if modo == 'demorado':
    filho = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
    pathlib.Path(os.environ['REGISTRO_TESTE'] + '.filho').write_text(str(filho.pid))
    time.sleep(10)
if modo == 'quebrado':
    print('saída não estruturada')
    sys.exit(0)
fontes = args[args.index('--arquivos') + 1:args.index('--')]
saida = pathlib.Path(args[args.index('--arquivo') + 1])
texto = '\\n'.join(f'Regra conferida na fonte indicada: {fonte}:1.' for fonte in fontes)
if modo == 'invalido':
    texto = 'Sem referências.'
if modo == 'mudou':
    pathlib.Path(fontes[0]).write_text('fonte alterada')
if modo in ('ok', 'invalido', 'mudou'):
    saida.write_text(texto, encoding='utf-8')
codigo = 'cota_insuficiente' if modo == 'cota' else ''
print(json.dumps({'tentativas': [{'destino': 'local', 'chamadas': 0 if modo == 'cota' else 1,
    'motivo_codigo': codigo}], 'motivo_codigo': codigo, 'relatorio': 'prévia incompleta',
    'artefato': '/arquivo/que/nao/deve/ser/lido'}))
sys.exit(4 if modo == 'cota' else 0)
'''


class Execucao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = pathlib.Path(self.tmp.name)
        self.projeto = self.pasta / 'projeto'
        self.projeto.mkdir()
        self.fonte = self.projeto / 'fonte.md'
        self.fonte.write_text('regra de teste', encoding='utf-8')
        self.raiz = self.pasta / 'jangada'
        (self.raiz / 'bin').mkdir(parents=True)
        (self.raiz / 'default/delegacao').mkdir(parents=True)
        shutil.copyfile(RAIZ / 'default/delegacao/validar.py', self.raiz / 'default/delegacao/validar.py')
        simulador = self.raiz / 'bin/jangada-delegar'
        simulador.write_text(SIMULADO, encoding='utf-8')
        simulador.chmod(0o700)
        self.estado = Estado(self.pasta / 'estado')
        self.addCleanup(self.estado.fechar)
        self.registro = self.pasta / 'registro.json'
        self.ambiente = patch.dict(os.environ, REGISTRO_TESTE=str(self.registro), MODO_TESTE='ok')
        self.ambiente.start()
        self.addCleanup(self.ambiente.stop)

    def tarefa(self, identificador='T1', **campos):
        return {'id': identificador, 'pedido': 'Leia a regra', 'papel': 'leitor',
                'capacidade': 'leitura_documental', 'risco': 1, 'qualidade': 'medium',
                'fontes': [str(self.fonte)],
                'hashes_fontes': {str(self.fonte): hashlib.sha256(self.fonte.read_bytes()).hexdigest()}, **campos}

    def rodar(self, perfil='balanced', limite=1):
        return executar(self.estado, self.projeto, self.raiz, perfil, limite)

    def test_preserva_relatorio_completo_sem_aprovar(self):
        self.estado.importar([self.tarefa(), self.tarefa('T2', dependencias=['T1'])])
        resultados = self.rodar(limite=2)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['status'], 'REVIEW_REQUIRED')
        item = self.estado.listar()[0]
        texto = self.estado.ler_artefato(item['artefato'])
        self.assertIn(str(self.fonte) + ':1', texto)
        self.assertNotIn('prévia', texto)
        self.assertEqual(self.estado.consumo('T1')['chamadas'], 1)
        self.estado.revisar('T1', 'conferido', True)
        self.assertEqual(self.rodar()[0]['tarefa'], 'T2')
        argumentos = json.loads(self.registro.read_text())['args']
        self.assertTrue(any('/artefatos/' in argumento for argumento in argumentos))

    def test_cota_nao_gasta_tentativa_e_preserva_espera(self):
        self.estado.importar([self.tarefa(max_tentativas=1)])
        with patch.dict(os.environ, MODO_TESTE='cota'):
            self.assertEqual(self.rodar()[0]['status'], 'WAITING_QUOTA')
        self.assertEqual(self.estado.listar()[0]['tentativas'], 0)
        self.assertEqual(self.rodar(), [])
        self.estado.alterar('T1', 'retomar')
        self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')

    def test_orcamento_compartilhado_entre_repeticoes(self):
        self.estado.importar([self.tarefa(max_chamadas=1)])
        with patch.dict(os.environ, MODO_TESTE='invalido'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.estado.alterar('T1', 'repetir')
        self.registro.unlink()
        self.assertEqual(self.rodar()[0]['status'], 'FAILED')
        self.assertFalse(self.registro.exists())

    def test_consumo_desconhecido_nao_repete(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_TESTE='quebrado'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.estado.alterar('T1', 'repetir')
        self.registro.unlink()
        self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.assertFalse(self.registro.exists())

    def test_timeout_preserva_consumo_desconhecido(self):
        self.estado.importar([self.tarefa(tempo_total=1)])
        with patch.dict(os.environ, MODO_TESTE='demorado'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.assertIsNone(self.estado.consumo('T1')['chamadas'])
        self.assertGreaterEqual(self.estado.consumo('T1')['segundos'], 1)
        pid = (self.pasta / 'registro.json.filho').read_text()
        processo = pathlib.Path('/proc') / pid / 'stat'
        self.assertTrue(not processo.exists() or processo.read_text().split(') ', 1)[1].startswith('Z'))

    def test_fonte_alterada_antes_e_durante_execucao(self):
        self.estado.importar([self.tarefa(), self.tarefa('T2')])
        with patch.dict(os.environ, MODO_TESTE='mudou'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.registro.unlink()
        self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.assertFalse(self.registro.exists())

    def test_perfis_nao_ampliam_permissao_da_sessao(self):
        self.estado.importar([self.tarefa(permitir_remoto=True)])
        with patch.dict(os.environ, JANGADA_DELEGAR='local', JANGADA_DELEGAR_ROTEAMENTO_ID='forjado'):
            self.rodar('offline')
        registro = json.loads(self.registro.read_text())
        self.assertEqual(registro['env']['JANGADA_DELEGAR'], 'local')
        self.assertIsNone(registro['env']['JANGADA_DELEGAR_ROTEAMENTO_ID'])
        self.assertNotIn('--permitir-remoto', registro['args'])
        self.assertIn('--destino', registro['args'])
        self.assertIn('local', registro['args'])

    def test_tarefa_principal_aguarda_sem_chamada(self):
        self.estado.importar([self.tarefa(qualidade='high')])
        self.assertEqual(self.rodar()[0]['status'], 'WAITING_REVIEWER')
        self.assertFalse(self.registro.exists())
        self.assertEqual(self.estado.listar()[0]['tentativas'], 0)

    def test_remoto_exige_permissao_na_chamada_e_no_plano(self):
        self.estado.importar([self.tarefa(permitir_remoto=True), self.tarefa('T2'),
                             self.tarefa('T3', permitir_remoto=True)])
        self.rodar('quality')
        self.assertNotIn('--permitir-remoto', json.loads(self.registro.read_text())['args'])
        executar(self.estado, self.projeto, self.raiz, 'quality', permitir_remoto=True)
        self.assertNotIn('--permitir-remoto', json.loads(self.registro.read_text())['args'])
        executar(self.estado, self.projeto, self.raiz, 'quality', permitir_remoto=True)
        self.assertIn('--permitir-remoto', json.loads(self.registro.read_text())['args'])

    def test_cli_executa_plano_sem_interpretar_pedido(self):
        shutil.copytree(RAIZ / 'default/orquestracao', self.raiz / 'default/orquestracao')
        plano = self.projeto / 'plano.json'
        plano.write_text(json.dumps([self.tarefa(pedido='$(touch invasao); --opcao')]), encoding='utf-8')
        ambiente = os.environ.copy()
        ambiente.update(JANGADA_PATH=str(self.raiz), XDG_STATE_HOME=str(self.pasta / 'state-cli'),
                        XDG_CONFIG_HOME=str(self.pasta / 'config-cli'))
        importacao = subprocess.run([str(RAIZ / 'bin/jangada-fila'), '--importar', str(plano)],
                                   cwd=self.projeto, env=ambiente, text=True, capture_output=True, timeout=30)
        self.assertEqual(importacao.returncode, 0, importacao.stderr)
        execucao = subprocess.run([str(RAIZ / 'bin/jangada-executar'), '--perfil', 'offline'],
                                 cwd=self.projeto, env=ambiente, text=True, capture_output=True, timeout=30)
        self.assertEqual(execucao.returncode, 0, execucao.stderr)
        self.assertEqual(json.loads(execucao.stdout)['resultados'][0]['status'], 'REVIEW_REQUIRED')
        self.assertFalse((self.projeto / 'invasao').exists())


if __name__ == '__main__':
    unittest.main()
