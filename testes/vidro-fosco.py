#!/usr/bin/env python3
"""Confere migração, fundos e preservação em pastas descartáveis."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as pasta:
    tmp = Path(pasta)
    config = tmp / 'config/jangada'
    env = dict(os.environ, JANGADA_PATH=str(repo), XDG_CONFIG_HOME=str(tmp / 'config'),
               XDG_STATE_HOME=str(tmp / 'estado'), HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='')

    def rodar(*args, sucesso=True, **extra):
        r = subprocess.run(args, env=dict(env, **extra), capture_output=True, text=True)
        assert (r.returncode == 0) == sucesso, r.stdout + r.stderr
        return r

    def gravar(relativo, texto):
        p = config / relativo
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto)
        return p

    modelos = repo / 'shell/temas/matugen/modelos'
    estilo = (repo / 'shell/waybar/style.css.modelo').read_text().replace('@JANGADA_PATH@', str(repo))
    barra = gravar('waybar/style.css', estilo)
    antigos = {}
    for rel, nome in [('fuzzel/fuzzel.ini', 'fuzzel.ini'), ('mako/config', 'mako')]:
        texto = (modelos / nome).read_text()
        texto = texto.replace('hex_stripped}}e0', 'hex_stripped}}f2').replace('hex}}e0', 'hex}}')
        texto = re.sub(r'\{\{.*?hex_stripped\}\}', '123456', texto)
        texto = re.sub(r'\{\{.*?hex\}\}', '#123456', texto)
        antigos[rel] = texto
        gravar(rel, texto)
    conf = gravar('jangada.conf', 'JANGADA_INTERFACE=componentes\n# pessoal\n')
    migracao = str(repo / 'migrations/202610111800-vidro-fosco.sh')
    antes = {p: p.read_bytes() for p in config.rglob('*') if p.is_file()}
    rodar('bash', migracao, JANGADA_SIMULAR='1')
    assert antes == {p: p.read_bytes() for p in config.rglob('*') if p.is_file()}
    rodar('bash', migracao)
    assert conf.read_text().endswith('# pessoal\n')
    assert '0.88' in barra.read_text()
    assert 'background=123456e0' in (config / 'fuzzel/fuzzel.ini').read_text()
    assert 'background-color=#123456e0' in (config / 'mako/config').read_text()
    fotos = {p: p.read_bytes() for p in config.rglob('*') if p.is_file()}
    rodar('bash', migracao)
    assert fotos == {p: p.read_bytes() for p in config.rglob('*') if p.is_file()}
    for rel in antigos:
        assert any(p.read_text() == antigos[rel] for p in (config / rel).parent.glob('*.bak'))
    print('ok: migração, cópias, repetibilidade e simulação')

    # Personalização integral sai da comparação com o modelo.
    personalizados = {}
    for rel, texto in antigos.items():
        personalizados[rel] = texto + '\n# ajuste pessoal\n'
        gravar(rel, personalizados[rel])
    barra.write_text(estilo + '\nwindow#waybar { font-size: 17px; }\n')
    rodar('bash', migracao)
    for rel, texto in personalizados.items():
        assert (config / rel).read_text() == texto
    assert 'jangada-vidro: início' not in barra.read_text()
    print('ok: migração mantém modelos personalizados')

    comando = str(repo / 'bin/jangada-vidro')
    conf.write_text('JANGADA_VIDRO=0\n')
    pessoal_barra = barra.read_bytes()
    r = rodar(comando, '--tema')
    assert 'mantido fundo pessoal' in r.stdout
    assert barra.read_bytes() == pessoal_barra
    rodar(comando, '--arquivos')
    assert 'background: alpha(@superficie, 1)' in barra.read_text()
    assert 'font-size: 17px' in barra.read_text()
    for rel in antigos:
        assert '# ajuste pessoal' in (config / rel).read_text()
        assert '123456ff' in (config / rel).read_text()
    conf.write_text('JANGADA_VIDRO=1\nJANGADA_VIDRO_ALPHA=0.72\n')
    rodar(comando, '--arquivos')
    assert '0.72' in barra.read_text()
    assert barra.read_text().count('jangada-vidro: início') == 1
    assert '123456b8' in (config / 'mako/config').read_text()
    conf.write_text('JANGADA_VIDRO_ALPHA=2\n')
    antes = barra.read_text()
    rodar(comando, '--arquivos', sucesso=False)
    assert barra.read_text() == antes
    conf.write_text('JANGADA_INTERFACE=noctalia\n')
    rodar(comando, '--arquivos')
    assert barra.read_text() == antes
    print('ok: desligar, ajustar, preservar opções e recusar alpha inválido')

# A composição de cores é uma verificação estática, sem inspeção de pixels.
import shutil
if not shutil.which('matugen'):
    print('pulado: contraste dos temas gerados exige matugen')
else:
    def rgb(cor):
        return tuple(int(cor[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def luminancia(cor):
        return sum(p * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
                   for p, c in zip((0.2126, 0.7152, 0.0722), cor))

    def contraste(texto, fundo):
        a, b = sorted((luminancia(texto), luminancia(fundo)))
        return (b + 0.05) / (a + 0.05)

    minimo = 100
    with tempfile.TemporaryDirectory() as pasta:
        tmp = Path(pasta)
        cfg = tmp / 'matugen.toml'
        cfg.write_text('[config]\nversion_check = false\n' + ''.join(
            f'\n[templates.{nome}]\ninput_path = "{repo}/shell/temas/matugen/modelos/{modelo}"\n'
            f'output_path = "{tmp}/{nome}"\n'
            for nome, modelo in [('waybar', 'waybar.css'), ('fuzzel', 'fuzzel.ini'), ('mako', 'mako')]))
        for cor in ('#4f8fba', '#fff4d5'):
            for modo in ('dark', 'light'):
                r = subprocess.run(['matugen', 'color', 'hex', cor, '-c', str(cfg), '-m', modo,
                                    '-t', 'scheme-fidelity'], capture_output=True, text=True)
                assert r.returncode == 0, r.stderr
                cores = dict(re.findall(r'@define-color (\w+) #(\w{6});', (tmp / 'waybar').read_text()))
                pares = [(cores['texto'], cores['superficie'], 0.88),
                         (cores['texto_suave'], cores['superficie'], 0.88),
                         (cores['primaria'], cores['superficie'], 0.88),
                         (cores['atencao'], cores['superficie'], 0.88),
                         (cores['texto_primario'], cores['primaria'], 1)]
                menu = dict(re.findall(r'^(\S+)=([0-9a-f]{8})$', (tmp / 'fuzzel').read_text(), re.M))
                pares.extend([(menu['text'][:6], menu['background'][:6], 224 / 255),
                              (menu['selection-text'][:6], menu['selection'][:6], 1),
                              (menu['selection-match'][:6], menu['selection'][:6], 1)])
                mako = dict(re.findall(r'^(\S+)=#([0-9a-f]{6,8})$', (tmp / 'mako').read_text(), re.M))
                pares.append((mako['text-color'], mako['background-color'][:6], 224 / 255))
                for texto, fundo, alpha in pares:
                    for papel in (0, 1):
                        composto = tuple(c * alpha + papel * (1 - alpha) for c in rgb(fundo))
                        valor = contraste(rgb(texto), composto)
                        minimo = min(minimo, valor)
                        assert valor >= 4.5, (cor, modo, texto, fundo, papel, valor)
    print(f'ok: contraste estático mínimo {minimo:.2f}:1, temas claros/escuros sobre branco/preto; foco, seleção e urgência')
    with tempfile.TemporaryDirectory() as pasta:
        tmp = Path(pasta)
        config = tmp / 'config/jangada'
        config.mkdir(parents=True)
        (config / 'jangada.conf').write_text('JANGADA_VIDRO=0\n')
        (config / 'fuzzel').mkdir()
        pessoal = '# ajustes a preservar\n[colors]\nbackground=123456ff\n'
        (config / 'fuzzel/fuzzel.ini').write_text(pessoal)
        ambiente = dict(os.environ, JANGADA_PATH=str(repo), XDG_CONFIG_HOME=str(tmp / 'config'),
                        XDG_STATE_HOME=str(tmp / 'estado'), JANGADA_SIMULAR='0',
                        HYPRLAND_INSTANCE_SIGNATURE='', WAYLAND_DISPLAY='',
                        DBUS_SESSION_BUS_ADDRESS='unix:path=/inexistente')
        executaveis = tmp / 'bin'
        executaveis.mkdir()
        data = executaveis / 'date'
        data.write_text('#!/bin/sh\nprintf "20261011-120000\\n"\n')
        data.chmod(0o755)
        ambiente['PATH'] = str(executaveis) + ':' + ambiente['PATH']
        r = subprocess.run([str(repo / 'bin/jangada-tema'), '--cor', '#4f8fba'],
                           env=ambiente, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert any(p.read_text() == pessoal for p in (config / 'fuzzel').glob('*.bak'))
        assert re.search(r'^background=[a-f0-9]{6}ff$', (config / 'fuzzel/fuzzel.ini').read_text(), re.M)
        assert 'alpha(@superficie, 1)' in (config / 'waybar/style.css').read_text()
        pessoal_barra = (config / 'waybar/style.css').read_text() + '\n.modules-left { background: #123456; }\n'
        (config / 'waybar/style.css').write_text(pessoal_barra)
        r = subprocess.run([str(repo / 'bin/jangada-tema'), '--cor', '#fff4d5'],
                           env=ambiente, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert 'mantido fundo pessoal' in r.stdout
        assert (config / 'waybar/style.css').read_text() == pessoal_barra
        print('ok: geração real do tema preserva folha pessoal e respeita vidro desligado e preserva original em cópias no mesmo segundo')

