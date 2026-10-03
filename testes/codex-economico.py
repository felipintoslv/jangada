#!/usr/bin/env python3
"""Confere alternativa Codex e roteamento com executores inteiramente simulados."""

import base64
import fcntl
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('worker_codex', RAIZ / 'default/delegacao/codex.py')
WORKER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(WORKER)


class Economico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = pathlib.Path(self.tmp.name)
        self.raiz = self.pasta / 'jangada'
        for nome in ('bin', 'default/delegacao', 'default/orquestracao'):
            (self.raiz / nome).mkdir(parents=True)
        for nome in ('bin/jangada-config', 'bin/jangada-delegar', 'default/delegacao/validar.py',
                     'bin/jangada-retomar', 'bin/jangada-router', 'default/delegacao/codex.py',
                     'default/orquestracao/cota_codex.py', 'default/orquestracao/cli.py',
                     'default/orquestracao/estado.py', 'default/orquestracao/executor.py', 'default/orquestracao/saude.py'):
            shutil.copy2(RAIZ / nome, self.raiz / nome)
        self.audit = self.pasta / 'execucao.json'
        self.fonte = self.pasta / 'fonte.md'
        self.fonte.write_text('Regra documentada na primeira linha.\n')
        self.casa = self.pasta / 'codex'
        self.casa.mkdir()
        exp = base64.urlsafe_b64encode(json.dumps({'exp': time.time() + 3600}).encode()).decode().rstrip('=')
        (self.casa / 'auth.json').write_text(json.dumps({'tokens': {
            'access_token': 'h.' + exp + '.s', 'id_token': 'identidade-falsa',
            'refresh_token': 'renovacao-original', 'account_id': 'conta-falsa'}}))
        self.bin = self.pasta / 'bin'
        self.bin.mkdir()
        self.config = self.pasta / 'config/jangada'
        self.config.mkdir(parents=True)
        (self.config / 'delegacao.json').write_text(json.dumps({'analise_documental': ['agy', 'codex-economico']}))
        self.ambiente = patch.dict(os.environ, JANGADA_PATH=str(self.raiz), JANGADA_DELEGAR='agy',
                                   JANGADA_CODEX_ECONOMICO_MODELO='modelo-economico-teste',
                                   JANGADA_CODEX_COTA_MIN='25', CODEX_HOME=str(self.casa),
                                   XDG_STATE_HOME=str(self.pasta / 'state'), XDG_CONFIG_HOME=str(self.pasta / 'config'),
                                   XDG_CACHE_HOME=str(self.pasta / 'cache'),
                                   PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                                   JANGADA_DELEGAR_IMPEDIMENTOS=json.dumps([
                                       {'destino': 'agy', 'motivo_codigo': 'cota_indisponivel', 'motivo': 'cota esgotada'}]))
        self.ambiente.start()
        self.addCleanup(self.ambiente.stop)
        self.stub_cota(20)
        self.stub_worker()

    def programa(self, caminho, corpo):
        caminho.write_text('#!' + sys.executable + '\n' + corpo)
        caminho.chmod(0o700)

    def stub_cota(self, usado):
        self.programa(self.bin / 'codex', '''import json, sys, time
assert sys.argv[-2:] == ['app-server', '--stdio']
assert json.loads(sys.stdin.readline())['method'] == 'initialize'
print(json.dumps({'id': 1, 'result': {}}), flush=True)
assert json.loads(sys.stdin.readline())['method'] == 'initialized'
assert json.loads(sys.stdin.readline())['method'] == 'account/rateLimits/read'
print(json.dumps({'id': 2, 'result': {'rateLimits': {'limitId': 'codex',
    'primary': {'usedPercent': ''' + repr(usado) + ''', 'resetsAt': int(time.time()) + 3600}}}}), flush=True)
sys.stdin.read()
''')

    def stub_worker(self, modo='ok'):
        self.programa(self.raiz / 'bin/jangada-codex', '''import json, os, pathlib, sys, time
args = sys.argv[1:]
assert args[:3] == ['--revisar', '--', 'codex']
assert args[args.index('--model') + 1] == 'modelo-economico-teste'
assert os.environ['HOME'] == os.environ['CODEX_HOME']
assert 'SEGREDO_TESTE' not in os.environ
assert json.loads((pathlib.Path(os.environ['CODEX_HOME']) / 'auth.json').read_text())['tokens']['refresh_token'] == ''
dados = json.loads(sys.stdin.read().splitlines()[-1])
pid_worker = os.getppid()
pid_shell = int((pathlib.Path('/proc') / str(pid_worker) / 'stat').read_text().split(') ')[1].split()[1])
pathlib.Path(''' + repr(str(self.audit)) + ''').write_text(json.dumps({'args': args, 'prompt': dados,
    'pid': os.getpid(), 'casa': os.environ['CODEX_HOME'], 'worker': pid_worker, 'bash': pid_shell}))
modo = ''' + repr(modo) + '''
if modo == 'demorado':
    time.sleep(60)
if modo == 'erro':
    sys.exit(1)
saida = pathlib.Path(args[args.index('--output-last-message') + 1])
texto = 'A regra possui conteúdo documentado na fonte fornecida. ' + dados['fontes'][0]['fonte'] + ':1'
if modo == 'sem-fonte':
    texto = 'Texto sem referência.'
if modo == 'gigante':
    texto = 'x' * 64001
saida.write_text(texto)
if modo != 'sem-completo':
    print('invalido' if modo == 'json-invalido' else json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 12}}))
if modo == 'duplicado':
    print(json.dumps({'type': 'turn.completed'}))
''')

    def executar(self, tempo=30):
        return WORKER.executar(self.raiz, self.pasta, 'Leia a regra', [str(self.fonte)], tempo)

    def delegar(self, extras=(), candidato=False):
        args = [str(self.raiz / 'bin/jangada-delegar'), '--capacidade', 'analise_documental', '--json']
        if candidato:
            args += ['--destino', 'codex-economico']
        args += list(extras) + ['--arquivos', str(self.fonte), '--', 'leitor', 'Leia a regra']
        return subprocess.run(args, cwd=self.pasta, capture_output=True, text=True, timeout=20)

    def test_modelo_explicito_fontes_limitadas_sem_ferramentas(self):
        with patch.dict(os.environ, SEGREDO_TESTE='nao-transmitir'):
            resultado = self.executar()
        self.assertEqual(resultado['motivo_codigo'], '')
        self.assertEqual(resultado['chamadas'], 1)
        self.assertEqual(resultado['tokens_saida'], 12)
        self.assertEqual(resultado['cota_antes'], 80)
        dados = json.loads(self.audit.read_text())['prompt']
        self.assertEqual(dados['fontes'], [{'fonte': str(self.fonte), 'linhas': '1: Regra documentada na primeira linha.'}])

    def test_modelo_ausente_ou_invalido_nao_escolhe_padrao(self):
        for modelo in ('', 'modelo com espaços', '--premium'):
            with self.subTest(modelo=modelo), patch.dict(os.environ, JANGADA_CODEX_ECONOMICO_MODELO=modelo):
                resultado = self.executar()
                self.assertEqual(resultado['motivo_codigo'], 'modelo_ausente')
                self.assertEqual(resultado['chamadas'], 0)
        self.assertFalse(self.audit.exists())

    def test_cota_baixa_esgotada_ou_desconhecida_nao_gera(self):
        for usado in (80, 100):
            self.stub_cota(usado)
            self.assertEqual(self.executar()['motivo_codigo'], 'cota_insuficiente')
        with patch.object(WORKER, 'consultar', side_effect=ValueError):
            resultado = self.executar()
            self.assertEqual(resultado['motivo_codigo'], 'cota_desconhecida')
            self.assertEqual(resultado['chamadas'], 0)
        self.assertFalse(self.audit.exists())

    def test_binario_e_contexto_grande_sao_recusados_sem_transmitir(self):
        for conteudo in (b'\x00PDF', b'%PDF-1.4\nobjeto', b'\xff', b'x' * 80001):
            self.fonte.write_bytes(conteudo)
            self.assertEqual(self.executar()['motivo_codigo'], 'contexto_insuficiente')
        self.assertFalse(self.audit.exists())

    def test_erro_conclusao_ausente_duplicada_e_saida_grande_nao_aprovam(self):
        for modo, esperado in (('erro', 'erro_execucao'), ('sem-completo', 'saida_invalida'),
                               ('duplicado', 'saida_invalida'), ('gigante', 'saida_invalida'),
                               ('json-invalido', 'saida_invalida')):
            with self.subTest(modo=modo):
                self.stub_worker(modo)
                resultado = self.executar()
                self.assertEqual(resultado['motivo_codigo'], esperado)
                self.assertEqual(resultado['chamadas'], 1)

    def test_tempo_limita_geracao(self):
        self.stub_worker('demorado')
        resultado = self.executar(1)
        self.assertEqual(resultado['motivo_codigo'], 'limite_tempo')
        self.assertEqual(resultado['chamadas'], 1)
        self.assertEqual(list(self.pasta.glob('.cota-codex-*')), [])

    def test_fallback_agy_esgotado_codex_configurado_sem_premium(self):
        resposta = self.delegar(['--permitir-remoto', '--permitir-codex'])
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        dados = json.loads(resposta.stdout)
        self.assertEqual(dados['destino'], 'codex-economico')
        self.assertEqual(dados['modelo'], 'modelo-economico-teste')
        self.assertEqual(dados['tentativas'][0]['motivo_codigo'], 'cota_indisponivel')
        self.assertEqual(dados['verificacao'], 'referencias_validas')
        self.assertEqual(dados['tokens_codex_entrada'], 10)
        self.assertFalse(dados['ferramentas_disponiveis'])

    def test_cada_permissao_e_perfil_local_barram_codex(self):
        for extras in ([], ['--permitir-remoto'], ['--permitir-codex']):
            with self.subTest(extras=extras):
                resposta = self.delegar(extras, candidato=True)
                self.assertEqual(resposta.returncode, 4, resposta.stderr)
        with patch.dict(os.environ, JANGADA_DELEGAR='local'):
            self.assertEqual(self.delegar(['--permitir-remoto', '--permitir-codex'], candidato=True).returncode, 4)
        self.assertFalse(self.audit.exists())

    def test_sem_fontes_na_saida_gate_reprova_e_preserva_relatorio(self):
        self.stub_worker('sem-fonte')
        resposta = self.delegar(['--permitir-remoto', '--permitir-codex'], candidato=True)
        self.assertEqual(resposta.returncode, 4, resposta.stderr)
        dados = json.loads(resposta.stdout)
        self.assertEqual(dados['tentativas'][0]['motivo_codigo'], 'saida_invalida')
        preservados = list((self.pasta / 'state/jangada/agentes').glob('delegacao-reprovada-*'))
        self.assertEqual(len(preservados), 1)
        self.assertEqual(preservados[0].read_text().strip(), 'Texto sem referência.')

    def test_previa_curta_preserva_artefato_conferido_completo(self):
        with patch.dict(os.environ, JANGADA_DELEGAR_PALAVRAS='5'):
            resposta = self.delegar(['--permitir-remoto', '--permitir-codex'], candidato=True)
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        dados = json.loads(resposta.stdout)
        self.assertTrue(dados['relatorio_cortado'])
        self.assertIn('relatório cortado', dados['relatorio'])
        self.assertIn(str(self.fonte) + ':1', pathlib.Path(dados['artefato']).read_text())

    def test_sem_capacidade_codex_e_recusado(self):
        resposta = subprocess.run([str(self.raiz / 'bin/jangada-delegar'), 'leitor', 'Leia',
                                   '--destino', 'codex-economico'], capture_output=True, text=True, timeout=10)
        self.assertEqual(resposta.returncode, 2)
        self.assertFalse(self.audit.exists())

    def test_executor_ocupado_nao_consulta_nem_gera(self):
        pasta = self.pasta / 'state/jangada/agentes'
        pasta.mkdir(parents=True)
        with (pasta / 'codex-economico.lock').open('w') as trava:
            fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
            resposta = self.delegar(['--permitir-remoto', '--permitir-codex'], candidato=True)
        self.assertEqual(resposta.returncode, 4, resposta.stderr)
        self.assertEqual(json.loads(resposta.stdout)['tentativas'][0]['motivo_codigo'], 'ocupado')
        self.assertFalse(self.audit.exists())

    def interromper_geracao(self, matar_shell):
        self.stub_worker('demorado')
        args = [str(self.raiz / 'bin/jangada-delegar'), '--capacidade', 'analise_documental', '--json',
                '--permitir-remoto', '--permitir-codex', '--arquivos', str(self.fonte), '--', 'leitor', 'Leia']
        pai = subprocess.Popen(args, cwd=self.pasta, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dados = None
        try:
            limite = time.monotonic() + 5
            while time.monotonic() < limite:
                try:
                    dados = json.loads(self.audit.read_text())
                    break
                except (OSError, ValueError):
                    time.sleep(0.01)
            self.assertIsNotNone(dados)
            if matar_shell:
                self.assertNotEqual(dados['bash'], dados['worker'])
                comando = (pathlib.Path('/proc') / str(dados['bash']) / 'cmdline').read_bytes().split(b'\x00')
                self.assertEqual(pathlib.Path(os.fsdecode(comando[0])).name, 'bash')
                self.assertIn(os.fsencode(str(self.raiz / 'bin/jangada-delegar')), comando)
                self.assertIsNone(pai.poll())
                os.kill(dados['bash'], 9)
            else:
                pai.kill()
            pai.communicate(timeout=5)
            limite = time.monotonic() + 5
            proc = pathlib.Path('/proc') / str(dados['pid']) / 'stat'
            while time.monotonic() < limite:
                try:
                    encerrado = proc.read_text().split(') ')[1].startswith('Z')
                except FileNotFoundError:
                    encerrado = True
                if encerrado and not pathlib.Path(dados['casa']).exists():
                    break
                time.sleep(0.01)
            self.assertTrue(encerrado)
            self.assertFalse(pathlib.Path(dados['casa']).exists())
        finally:
            if pai.poll() is None:
                pai.kill()
            pai.communicate(timeout=5)

    def test_queda_do_orquestrador_encerra_geracao_e_remove_credenciais(self):
        self.interromper_geracao(False)

    def test_kill_no_shell_filho_encerra_geracao_com_orquestrador_vivo(self):
        self.interromper_geracao(True)

    def test_cli_atualiza_cota_codex_com_perfil_remoto_padrao(self):
        self.programa(self.bin / 'agy', 'import json\nprint(json.dumps({"command":{"data":{"groups":[{"buckets":[{"id":"gemini-5h","remaining_fraction":0.5}]}]}}}))\n')
        for perfil in ('', None):
            ambiente = os.environ.copy()
            ambiente['JANGADA_OLLAMA_URL'] = 'url-invalida'
            ambiente['XDG_STATE_HOME'] = str(self.pasta / ('state-vazio' if perfil == '' else 'state-ausente'))
            if perfil is None:
                ambiente.pop('JANGADA_DELEGAR', None)
            else:
                ambiente['JANGADA_DELEGAR'] = perfil
            resultado = subprocess.run([str(self.raiz / 'bin/jangada-retomar'), '--projeto', str(self.pasta),
                                        '--atualizar', '--permitir-remoto', '--permitir-codex'],
                                       env=ambiente, capture_output=True, text=True, timeout=20)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            status = subprocess.run([str(self.raiz / 'bin/jangada-router'), 'status'], env=ambiente,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(status.returncode, 0, status.stderr)
            item = next(p for p in json.loads(status.stdout)['provedores'] if p['id'] == 'codex')
            self.assertEqual(item['status'], 'AVAILABLE')
            self.assertEqual(item['cota'], 80)



if __name__ == '__main__':
    unittest.main()
