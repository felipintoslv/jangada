#!/usr/bin/env python3
"""Confere supervisão e retomada com executores simulados, sem rede."""

import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'default/orquestracao'))
from estado import Estado
from executor import executar
from metricas_projeto import resumir
from supervisao import parecer_valido, aprovacao_valida
from acompanhamento import acompanhar
from saude import Saude

SIMULADO = '''#!/usr/bin/env python3
import hashlib,json,os,pathlib,sys,time
a=sys.argv[1:]
saida=pathlib.Path(a[a.index('--arquivo')+1])
revisao=saida.name=='parecer.json'
fontes=a[a.index('--arquivos')+1:a.index('--')]
destino=a[a.index('--destino')+1] if revisao else os.environ.get('AUTOR_TESTE','local')
with open(os.environ['REGISTRO_SUPERVISAO'],'a') as registro:
    registro.write(json.dumps({'fase':'revisao' if revisao else 'autor','destino':destino,
                              'saldo':os.environ['JANGADA_DELEGAR_CHAMADAS_MAX']})+'\\n')
modo=os.environ.get('MODO_SUPERVISAO','ok')
registro={'destino':destino,'modelo':'simulado','tentativas':[{'destino':destino,'chamadas':1}]}
if revisao and modo=='quota':
    registro.update(motivo_codigo='cota_insuficiente',recusa=True)
    registro['tentativas'][0].update(chamadas=0,motivo_codigo='cota_insuficiente')
    print(json.dumps(registro));sys.exit(4)
if revisao:
    pedido=json.loads(a[-1].split('\\n')[-1])
    justificativa='O conteúdo corresponde às evidências indicadas: '+', '.join(f'{f}:1' for f in fontes)
    parecer={'task_id':pedido['task_id'],'relatorio_sha256':pedido['relatorio_sha256'],
             'decisao':'APPROVED','criterios':{c:{'resultado':'PASS','justificativa':justificativa}
                 for c in ('fidelidade','completude','extrapolacoes')},'observacoes':[]}
    if modo=='erro':
        parecer['decisao']='REVISE';parecer['criterios']['fidelidade']['resultado']='FAIL'
    elif modo=='ambiguo':
        parecer['decisao']='ESCALATE';parecer['criterios']['fidelidade']['resultado']='INDETERMINATE'
    elif modo=='hash':parecer['relatorio_sha256']='0'*64
    elif modo=='referencias':
        for c in parecer['criterios'].values():c['justificativa']='O conteúdo está bom e suficiente para todos.'
    elif modo=='observacao':parecer['observacoes']=['Falta uma verificação.']
    elif modo=='timeout':time.sleep(5)
    elif modo=='desconhecido':registro['tentativas'][0]['chamadas']=None
    elif modo=='fonte_alterada':pathlib.Path(fontes[0]).write_text('alterada')
    saida.write_text('{quebrado' if modo=='json' else json.dumps(parecer,ensure_ascii=False))
else:
    saida.write_text('Resumo da regra conferida: '+', '.join(f'{f}:1' for f in fontes))
print(json.dumps(registro))
'''


class Supervisao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta = pathlib.Path(self.tmp.name)
        self.projeto = self.pasta / 'projeto'
        self.projeto.mkdir()
        self.fonte = self.projeto / 'fonte.md'
        self.fonte.write_text('Uma regra documentada.\n')
        self.raiz = self.pasta / 'jangada'
        (self.raiz / 'bin').mkdir(parents=True)
        (self.raiz / 'default/delegacao').mkdir(parents=True)
        shutil.copyfile(RAIZ / 'default/delegacao/validar.py', self.raiz / 'default/delegacao/validar.py')
        shutil.copyfile(RAIZ / 'default/delegacao/roteamento.json', self.raiz / 'default/delegacao/roteamento.json')
        comando = self.raiz / 'bin/jangada-delegar'
        comando.write_text(SIMULADO)
        comando.chmod(0o700)
        self.estado = Estado(self.pasta / 'estado')
        self.addCleanup(self.estado.fechar)
        self.log = self.pasta / 'chamadas.jsonl'
        ambiente = patch.dict(os.environ, JANGADA_DELEGAR='agy', JANGADA_CODEX_ECONOMICO_MODELO='',
                              REGISTRO_SUPERVISAO=str(self.log), MODO_SUPERVISAO='ok', AUTOR_TESTE='local')
        ambiente.start()
        self.addCleanup(ambiente.stop)

    def tarefa(self, id='T1', **campos):
        return {'id':id, 'papel':'leitor', 'capacidade':'resumo_curto', 'risco':1, 'qualidade':'medium',
                'pedido':'Resuma a regra sem extrapolar.', 'fontes':[str(self.fonte)],
                'hashes_fontes':{str(self.fonte):hashlib.sha256(self.fonte.read_bytes()).hexdigest()},
                'intermediaria':True, 'supervisao_automatica':True, 'permitir_remoto':True, **campos}

    def rodar(self, **opcoes):
        return executar(self.estado, self.projeto, self.raiz, permitir_remoto=True,
                        supervisao_automatica=True, **opcoes)

    def chamadas(self):
        return [json.loads(linha) for linha in self.log.read_text().splitlines()]

    def test_supervisor_aprova_intermediario_e_libera_dependencia(self):
        self.estado.importar([self.tarefa(), self.tarefa('T2', dependencias=['T1'])])
        resultado = self.rodar()[0]
        self.assertEqual(resultado['status'], 'COMPLETED')
        self.assertEqual(resultado['metricas']['chamadas'], 2)
        self.assertEqual([c['fase'] for c in self.chamadas()], ['autor', 'revisao'])
        self.assertEqual(self.estado.reservar()[0]['id'], 'T2')
        metricas = resumir(self.estado)
        self.assertEqual(metricas['supervisoes_aprovadas'], 1)
        self.assertEqual(metricas['revisoes_aprovadas'], 0)
        self.assertEqual(metricas['desempenho'], [])

    def test_sem_opcao_explicita_nao_supervisiona(self):
        self.estado.importar([self.tarefa()])
        resultado = executar(self.estado, self.projeto, self.raiz, permitir_remoto=True)[0]
        self.assertEqual(resultado['status'], 'REVIEW_REQUIRED')
        self.assertEqual(len(self.chamadas()), 1)

    def test_ollama_nunca_e_revisor(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, JANGADA_DELEGAR='local'):
            self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')
            self.assertEqual(self.rodar(), [])
        self.assertEqual(len(self.chamadas()), 1)

    def test_revisor_igual_ao_autor_nao_aprova(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, AUTOR_TESTE='agy'):
            self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')
        self.assertEqual(len(self.chamadas()), 1)

    def test_codex_configurado_revisa_autor_agy(self):
        self.estado.importar([self.tarefa(permitir_codex=True)])
        with patch.dict(os.environ, AUTOR_TESTE='agy', JANGADA_CODEX_ECONOMICO_MODELO='configurado'):
            resultado = self.rodar(permitir_codex=True)[0]
        self.assertEqual(resultado['status'], 'COMPLETED')
        self.assertEqual(resultado['supervisao']['executor'], 'codex-economico')

    def test_quota_retorna_e_revisa_sem_repetir_autor(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_SUPERVISAO='quota'):
            self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')
        artefato = self.estado.listar()[0]['artefato']
        self.assertEqual(self.rodar()[0]['status'], 'COMPLETED')
        self.assertEqual([c['fase'] for c in self.chamadas()], ['autor', 'revisao', 'revisao'])
        self.assertEqual(self.estado.listar()[0]['artefato'], artefato)
        self.assertEqual(self.estado.consumo('T1')['chamadas'], 2)
        self.assertEqual(resumir(self.estado)['chamadas_confirmadas'], 2)

    def test_acompanhamento_retoma_supervisao_quando_quota_retorna(self):
        global_estado = Estado(self.pasta / 'saude')
        self.addCleanup(global_estado.fechar)
        saude = Saude(global_estado)
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_SUPERVISAO='quota'):
            self.assertEqual(self.rodar(saude=saude)[0]['status'], 'REVIEW_REQUIRED')
        def atualizar(remoto):
            self.assertTrue(remoto)
            saude.observar('agy', 'AVAILABLE', 'quota simulada retornou', cota=100)
        with patch.object(saude, 'atualizar', side_effect=atualizar) as sonda:
            resultado = acompanhar(self.estado, self.projeto, self.raiz, self.pasta / 'config', saude,
                                  limite=1, duracao=60, permitir_remoto=True, supervisao_automatica=True)
        sonda.assert_called_once_with(True)
        self.assertEqual(resultado['estados'], {'COMPLETED':1})
        self.assertEqual([c['fase'] for c in self.chamadas()], ['autor', 'revisao', 'revisao'])

    def test_erro_do_relatorio_exige_correcao(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_SUPERVISAO='erro'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')
        self.assertEqual(self.rodar(), [])

    def test_ambiguidades_nao_sao_repetidas_ate_obter_aprovacao(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_SUPERVISAO='ambiguo'):
            self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')
        self.assertEqual(self.rodar(), [])
        self.assertEqual(len(self.chamadas()), 2)

    def test_pareceres_invalidos_nao_aprovam(self):
        for modo in ('json','hash','referencias','observacao','desconhecido'):
            with self.subTest(modo=modo), patch.dict(os.environ, MODO_SUPERVISAO=modo):
                self.estado.importar([self.tarefa(modo)])
                resultado = self.rodar()[0]
                self.assertEqual(resultado['status'], 'REVIEW_REQUIRED')
                self.assertEqual(resultado['tarefa'], modo)
                self.assertFalse(resultado['supervisao']['aguardando'])

    def test_orcamento_inclui_autor_e_revisor(self):
        self.estado.importar([self.tarefa(max_chamadas=1)])
        self.assertEqual(self.rodar()[0]['status'], 'REVIEW_REQUIRED')
        self.assertEqual(len(self.chamadas()), 1)
        self.assertEqual(self.rodar(), [])

    def test_timeout_preserva_relatorio_e_consumo_desconhecido(self):
        self.estado.importar([self.tarefa(tempo_total=3)])
        with patch.dict(os.environ, MODO_SUPERVISAO='timeout'):
            resultado = self.rodar()[0]
        self.assertEqual(resultado['status'], 'REVIEW_REQUIRED')
        self.assertIsNone(self.estado.consumo('T1')['chamadas'])
        self.assertIsNotNone(self.estado.listar()[0]['artefato'])
        self.assertEqual(self.rodar(), [])

    def test_fonte_alterada_pelo_revisor_impede_conclusao(self):
        self.estado.importar([self.tarefa()])
        with patch.dict(os.environ, MODO_SUPERVISAO='fonte_alterada'):
            self.assertEqual(self.rodar()[0]['status'], 'REVISION_REQUIRED')

    def test_nao_importa_supervisao_de_tarefa_final_ou_critica(self):
        for campos in ({'intermediaria':False}, {'risco':3}, {'qualidade':'high'}, {'intermediaria':'sim'}):
            with self.subTest(campos=campos), self.assertRaises(ValueError):
                self.estado.importar([self.tarefa(**campos)])
        self.assertEqual(self.estado.listar(), [])

    def test_parecer_com_chave_duplicada_e_rejeitado(self):
        with self.assertRaises(ValueError):
            parecer_valido('{"task_id":"T1","task_id":"T2"}', self.tarefa(), 'texto')

    def test_aprovacao_do_worker_nao_substitui_supervisor(self):
        self.estado.importar([self.tarefa()])
        _, dono = self.estado.reservar()
        with self.assertRaises(ValueError):
            self.estado.finalizar('T1', dono, 'COMPLETED', {'metricas':{'chamadas':1},
                                 'delegacao':{'destino':'local'}, 'confidence':1}, 'texto')
        self.assertFalse(aprovacao_valida(self.tarefa(), 'texto', {'supervisao':[]}))


if __name__ == '__main__':
    unittest.main()
