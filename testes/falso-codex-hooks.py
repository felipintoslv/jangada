"""Servidor mínimo para os testes do adaptador, sem rede nem modelos."""
import hashlib
import json
import os
import sys
import tomllib

hooks = []
for i, arg in enumerate(sys.argv):
    if arg == "-c" and sys.argv[i + 1].startswith("hooks."):
        config = tomllib.loads(sys.argv[i + 1])["hooks"]
        for event, groups in config.items():
            if event == "state":
                continue
            for group in groups:
                for handler in group["hooks"]:
                    hooks.append({"key": "teste:" + event, "source": "sessionFlags",
                                  "eventName": event, "command": handler["command"],
                                  "currentHash": "sha256:" + hashlib.sha256((event + handler["command"]).encode()).hexdigest(),
                                  "trustStatus": "untrusted" if os.environ.get("FALSO_HOOKS_NAO_CONFIADOS") else "trusted"})

if hooks and os.environ.get("FALSO_HOOK_DESABILITADO"):
    hooks[0]["enabled"] = False

if os.environ.get("FALSO_HOOKS_EXTERNOS"):
    hooks.append({"key": "externo:nao-aprovado", "source": "user", "eventName": "Stop",
                  "command": "comando externo", "currentHash": "sha256:externo",
                  "trustStatus": "untrusted"})

for line in sys.stdin:
    request = json.loads(line)
    result = {"data": [{"hooks": hooks}]} if request["method"] == "hooks/list" else {}
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
