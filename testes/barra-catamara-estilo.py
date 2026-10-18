#!/usr/bin/env python3
"""Confere a migração que tira do style.css pessoal o bloco antigo do Catamarã."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
MIGRACAO = REPO / 'migrations/202610172210-barra-catamara-estilo.sh'
ANTES = '''@import url("base.css");

/* jangada-vidro */
window#waybar {
  background: alpha(@superficie, 0.80);
}

'''
BLOCO = '''/* Catamarã: estados ativo, aviso (entregas pendentes) e erro (portão reprovado). */
#custom-catamara {
  padding: 0 8px;
  border-radius: 8px;
  color: @primaria;
  background: alpha(@primaria, 0.12);
  border: 1px solid alpha(@primaria, 0.30);
}

#custom-catamara:hover {
  background: alpha(@primaria, 0.22);
}

#custom-catamara.aviso {
  color: @atencao;
  background: alpha(@atencao, 0.16);
  border: 1px solid alpha(@atencao, 0.40);
  font-weight: bold;
}

#custom-catamara.erro {
  color: @superficie;
  background: @atencao;
  border: 1px solid @atencao;
  font-weight: bold;
}

'''
DEPOIS = '''window#waybar.vertical #custom-menu,
window#waybar.vertical #custom-catamara,
window#waybar.vertical #clock {
  padding: 4px 0;
}
'''


class Estilo(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.alvo = Path(self.pasta.name) / 'jangada/waybar/style.css'
        self.alvo.parent.mkdir(parents=True)
        self.ambiente = dict(os.environ, XDG_CONFIG_HOME=self.pasta.name,
                             JANGADA_PATH=str(REPO), JANGADA_SIMULAR='0')

    def migrar(self, simular=False):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        resultado = subprocess.run(['bash', str(MIGRACAO)], env=ambiente,
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return resultado

    def copias(self):
        return list(self.alvo.parent.glob('style.css.jangada-*.bak'))

    def mantido(self, texto, aviso):
        self.alvo.write_text(texto)
        resultado = self.migrar()
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual('mantido' in resultado.stderr, aviso)
        self.assertEqual(self.alvo.read_text(), texto)
        self.assertEqual(self.copias(), [])

    def test_bloco_exato_sai(self):
        antes = ANTES + BLOCO + DEPOIS
        self.alvo.write_text(antes)
        self.migrar(simular=True)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])
        self.migrar()
        self.assertEqual(self.alvo.read_text(), ANTES + DEPOIS)
        self.assertEqual([c.read_text() for c in self.copias()], [antes])
        resultado = self.migrar()
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual(self.alvo.read_text(), ANTES + DEPOIS)
        self.assertEqual(len(self.copias()), 1)

    def test_espaco_no_fim_da_linha_e_fim_do_arquivo(self):
        bloco = BLOCO.replace('  padding: 0 8px;\n', '  padding: 0 8px;  \n')
        self.alvo.write_text(ANTES + bloco.rstrip('\n') + '\n')
        self.migrar()
        self.assertEqual(self.alvo.read_text(), ANTES.rstrip('\n') + '\n')

    def test_bloco_alterado_fica(self):
        alterado = BLOCO.replace('font-weight: bold;', 'font-weight: normal;', 1)
        self.mantido(ANTES + alterado + DEPOIS, aviso=True)
        recuado = BLOCO.replace('  padding: 0 8px;', '    padding: 0 8px;')
        self.mantido(ANTES + recuado + DEPOIS, aviso=True)

    def test_sem_bloco_fica(self):
        self.mantido(ANTES + DEPOIS, aviso=False)

    def test_sem_arquivo(self):
        resultado = self.migrar()
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertFalse(self.alvo.exists())


if __name__ == '__main__':
    unittest.main()
