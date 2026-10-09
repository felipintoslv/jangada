#!/usr/bin/python3
"""Barramento efêmero: uma credencial, leitura da origem e Unlock apenas sintético."""
import hashlib,json,os,select,subprocess,sys,tempfile
from pathlib import Path
import dbus,dbus.service,dbus.mainloop.glib
from gi.repository import GLib
S='org.freedesktop.secrets'; B='/org/freedesktop/secrets'; I=B+'/collection/login/credencial'; C=B+'/collection/login'; T=B+'/session/ensaio'
OUT=Path(__file__).resolve().parents[1]
def main():
 raiz=Path(sys.argv[1]).resolve()
 if raiz.parent!=Path('/tmp') or not raiz.name.startswith('jreal-'):raise ValueError('Raiz inválida')
 env=json.loads((raiz/'ambiente.json').read_text())
 for k in ('HOME','XDG_RUNTIME_DIR','TMPDIR','JANGADA_PATH'):
  if not Path(env[k]).resolve().is_relative_to(raiz):raise ValueError('Estado externo')
 dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
 host=dbus.bus.BusConnection(os.environ['DBUS_SESSION_BUS_ADDRESS'])
 api=dbus.Interface(host.get_object(S,B),'org.freedesktop.Secret.Service')
 livres,travados=api.SearchItems(dbus.Dictionary({},signature='ss'))
 selecionados=[]
 for p in livres:
  props=dbus.Interface(host.get_object(S,p),'org.freedesktop.DBus.Properties')
  attrs=props.Get('org.freedesktop.Secret.Item','Attributes')
  if attrs.get('service')=='gemini' and 'username' in attrs and not props.Get('org.freedesktop.Secret.Item','Locked'):selecionados.append((p,attrs))
 if len(selecionados)!=1:
  print(json.dumps({'classificacao':'BLOQUEADO','motivo':'Exige exatamente uma credencial gemini já desbloqueada; nenhum desbloqueio real solicitado'}));return 2
 origem,attrs=selecionados[0]
 pasta=Path(tempfile.mkdtemp(prefix='auth-',dir=env['XDG_RUNTIME_DIR']));pasta.chmod(0o700)
 socket=pasta/'bus'
 daemon=subprocess.Popen(['/usr/bin/dbus-daemon','--session','--nofork','--nopidfile','--address=unix:path='+str(socket),'--print-address=1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
 filho=None
 eventos={'segredos_lidos':0,'unlock_sintetico':0,'escritas_na_origem':0,'chamadas':{},'buscas_sem_correspondencia':0}
 def contar(nome):eventos['chamadas'][nome]=eventos['chamadas'].get(nome,0)+1
 try:
  if not select.select([daemon.stdout],[],[],8)[0]:raise RuntimeError('Barramento não iniciou no prazo')
  endereco=daemon.stdout.readline().strip()
  if not endereco.startswith('unix:path='+str(socket)):raise RuntimeError('Barramento sintético inválido')
  privado=dbus.bus.BusConnection(endereco);nome=dbus.service.BusName(S,bus=privado)
  class Objeto(dbus.service.Object):
   def __init__(self,path,propriedades):self.propriedades=propriedades;super().__init__(nome,path)
   @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
   def Get(self,interface,chave):
    contar('Properties.Get');return self.propriedades[str(chave)]
   @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
   def GetAll(self,interface):return self.propriedades
  class Raiz(Objeto):
   @dbus.service.method('org.freedesktop.Secret.Service',in_signature='sv',out_signature='vo')
   def OpenSession(self,algoritmo,entrada):
    contar('OpenSession:'+str(algoritmo))
    if algoritmo!='plain':raise dbus.exceptions.DBusException('Somente sessão plain local',name=S+'.Error.NotSupported')
    return dbus.String(''),dbus.ObjectPath(T)
   @dbus.service.method('org.freedesktop.Secret.Service',in_signature='s',out_signature='o')
   def ReadAlias(self,alias):return dbus.ObjectPath(C if alias in ('default','login') else '/')
   @dbus.service.method('org.freedesktop.Secret.Service',in_signature='a{ss}',out_signature='aoao')
   def SearchItems(self,filtro):return self.buscar(filtro),[]
   def buscar(self,filtro):
    contar('SearchItems')
    corresponde=all(attrs.get(k)==v for k,v in filtro.items())
    if not corresponde:eventos['buscas_sem_correspondencia']+=1
    return [dbus.ObjectPath(I)] if corresponde else []
   @dbus.service.method('org.freedesktop.Secret.Service',in_signature='ao',out_signature='aoo')
   def Unlock(self,caminhos):
    if any(str(p) not in (I,C,B+'/aliases/default') for p in caminhos):raise dbus.exceptions.DBusException('Objeto não autorizado',name=S+'.Error.NoSuchObject')
    eventos['unlock_sintetico']+=1
    return caminhos,dbus.ObjectPath('/')
  class Colecao(Objeto):
   @dbus.service.method('org.freedesktop.Secret.Collection',in_signature='a{ss}',out_signature='ao')
   def SearchItems(self,filtro):return root.buscar(filtro)
  class Item(Objeto):
   @dbus.service.method('org.freedesktop.Secret.Item',in_signature='o',out_signature='(oayays)')
   def GetSecret(self,sessao):
    if sessao!=T:raise dbus.exceptions.DBusException('Sessão inválida',name=S+'.Error.NoSession')
    _,hs=api.OpenSession('plain',dbus.String(''))
    try:
     segredo=dbus.Interface(host.get_object(S,origem),'org.freedesktop.Secret.Item').GetSecret(hs)
     eventos['segredos_lidos']+=1
     return (dbus.ObjectPath(T),segredo[1],segredo[2],segredo[3])
    finally:dbus.Interface(host.get_object(S,hs),'org.freedesktop.Secret.Session').Close()
  class Sessao(Objeto):
   @dbus.service.method('org.freedesktop.Secret.Session',in_signature='',out_signature='')
   def Close(self):pass
  root=Raiz(B,{'Collections':dbus.Array([dbus.ObjectPath(C)],signature='o')})
  col=Colecao(C,{'Locked':dbus.Boolean(False),'Items':dbus.Array([dbus.ObjectPath(I)],signature='o'),'Label':dbus.String('Ensaio sintético')})
  alias=Colecao(B+'/aliases/default',col.propriedades)
  item=Item(I,{'Locked':dbus.Boolean(False),'Attributes':attrs,'Label':dbus.String('Credencial selecionada')})
  sessao=Sessao(T,{})
  childenv=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=endereco)
  filho=subprocess.Popen(['/usr/bin/python3','-B',str(OUT/'scripts/verificar_agy_real.py'),str(raiz),'--barramento-sintetico']+(['--sondar-chaveiro'] if '--diagnosticar' in sys.argv[2:] else []),env=childenv)
  loop=GLib.MainLoop()
  def verificar():
   if filho.poll() is not None:loop.quit();return False
   return True
  GLib.timeout_add(200,verificar);loop.run()
  print(json.dumps({'ponte_temporaria':True,'estado':eventos,'codigo_teste':filho.returncode,'origem_somente_leitura':True},indent=2))
  (OUT/'evidencias'/raiz.name/'ponte-agy-resumo.json').write_text(json.dumps(eventos,indent=2))
  return filho.returncode
 finally:
  if filho is not None and filho.poll() is None:filho.terminate();filho.wait(timeout=10)
  daemon.terminate();daemon.wait(timeout=10)
if __name__=='__main__':raise SystemExit(main())
