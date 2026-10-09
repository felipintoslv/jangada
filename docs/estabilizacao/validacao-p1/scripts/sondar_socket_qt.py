"""Diagnóstico opcional; somente sockets sintéticos em diretório temporário."""
import json
import tempfile
from pathlib import Path
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtNetwork import QLocalServer
app=QCoreApplication([])
resultados=[]
with tempfile.TemporaryDirectory(prefix='jq-') as pasta:
 for tamanho in (80,107,120):
  nome=pasta+'/'+'s'*(tamanho-len(pasta.encode())-1)
  servidor=QLocalServer()
  ok=servidor.listen(nome)
  resultados.append({'bytes':len(nome.encode()),'listen':ok,'erro':servidor.errorString()})
  servidor.close()
print(json.dumps(resultados,ensure_ascii=False,indent=2))
