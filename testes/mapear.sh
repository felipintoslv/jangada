#!/usr/bin/env bash
# Testa a máscara de dados sensíveis do jangada-mapear (--mascarar): nenhum
# segredo das entradas de exemplo sobra na saída, e o texto comum passa sem
# alteração.
#
# Uso: testes/mapear.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }

# Cada linha tem um segredo; o segundo arquivo lista o trecho que não pode
# sobrar na saída, na mesma ordem.
# Os segredos de exemplo são falsos, mas o gitleaks os reconheceria no
# arquivo: o $z vazio parte cada um, e o texto montado é o de sempre.
z=
entrada=$(cat <<EOF
export AWS_ACCESS_KEY_ID=AK${z}IAIOSFODNN7EXAMPLE
x AS${z}IAABCDEFGHIJKLMNOP y
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
GITHUB=github${z}_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz
t gh${z}p_abcdefghijklmnopqrstuvwxyz0123456789 fim
t gh${z}o_abcdefghijklmnopqrstuvwxyz0123456789 fim
t gh${z}s_abcdefghijklmnopqrstuvwxyz0123456789 fim
gl gl${z}pat-abcdefghij1234567890
//registry.npmjs.org/:_authToken=np${z}m_abcdefghijklmnopqrstuvwxyz0123456789
npm np${z}m_ZYXWVUTSRQPONMLKJIHGFEDCBA0123456789 fim
hf h${z}f_abcdefghijklmnopqrstuvwxyzABCDEFGH
ANTH sk${z}-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789-_ABCD
OPENAI sk${z}-proj-abcdefghijklmnopqrstuvwxyz0123
jwt ey${z}JhbGciOiJIUzI1NiJ9.ey${z}JzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U
-----BEGIN OPENSSH PRIV${z}ATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
-----END OPENSSH PRIV${z}ATE KEY-----
-----BEGIN RSA PRIV${z}ATE KEY-----
MIIEowIBAAKCAQEAuRSAlinhaSecretaDoMeio
-----END RSA PRIV${z}ATE KEY-----
{"private_key": "-----BEGIN PRIV${z}ATE KEY-----\nMIIEvChaveDeContaDeServico\n-----END PRIV${z}ATE KEY-----\n", "a": 1}
url = https://joao:s3nh4forte@example.com/repo.git
db postgres://user:senhaDoBanco@db:5432/app
curl -H "Authorization: Bear${z}er abcdef1234567890xyz"
Authorization: Bear${z}er tokenDoCabecalho123
Authorization: Bas${z}ic dXN1YXJpbzpzZW5oYQ==
"secretKey": "segredo com espacos",
"privateKey": "chavePrivadaXYZ",
password = "uma senha com espacos"
senha='outra senha aqui'
"token": "com \"aspas\" dentro"
api_key: abc123chave
"client_secret":"clienteSecreto"
EOF
)
segredos=(
  IOSFODNN7EXAMPLE ABCDEFGHIJKLMNOP wJalrXUtnFEMI 11ABCDEFG0123456789
  abcdefghijklmnopqrstuvwxyz0123456789 abcdefghij1234567890
  ZYXWVUTSRQPONMLKJIHGFEDCBA hf_abcdefghijklmnop api03 sk-proj-abcdef
  OiJIUzI1NiJ9 dozjgNryP4J3 b3BlbnNzaC1rZXktdjEAAAAABG5vbmU aSecretaDoMeio
  MIIEvChaveDeContaDeServico s3nh4forte senhaDoBanco abcdef1234567890xyz
  tokenDoCabecalho123 dXN1YXJpbzpzZW5oYQ segredo espacos chavePrivadaXYZ
  "uma senha" "outra senha" "senha aqui" aspas dentro abc123chave clienteSecreto
)

saida="$(bin/jangada-mapear --mascarar <<<"$entrada")"
for s in "${segredos[@]}"; do
  if grep -qF -- "$s" <<<"$saida"; then
    falha "sobrou na saída: $s"
  else
    ok "mascarado: $s"
  fi
done
if grep -qF "[chave privada removida]" <<<"$saida"; then
  ok "bloco de chave privada substituído"
else
  falha "bloco de chave privada substituído"
fi
if [[ "$(grep -cF 'AKIA***' <<<"$saida")" -eq 1 ]]; then
  ok "prefixo da chave AWS mantido para identificação"
else
  falha "prefixo da chave AWS mantido para identificação"
fi

# Texto comum que parece com segredo mas não é: tem de passar igual.
comum=$(cat <<'EOF'
# task-runner-configuration-file, npm_config_cache, hf_hub_cache
max_tokens = 4096
fonte = "JetBrains Mono"; gap = 10
https://example.com:8080/caminho e ssh://git@github.com/usuario/repo.git
The token is used for auth. Basic usage here. Bearer tokens expire.
bind = SUPER, Return, exec, ghostty
"keybinds": {"secretaria": "abrir"}, "tokenizer": "bpe"
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA
-----END PUBLIC KEY-----
EOF
)
if [[ "$(bin/jangada-mapear --mascarar <<<"$comum")" == "$comum" ]]; then
  ok "texto comum sem alteração"
else
  falha "texto comum alterado:"
  diff <(printf '%s\n' "$comum") <(bin/jangada-mapear --mascarar <<<"$comum")
fi

if ((falhas)); then
  echo "mapear: $falhas falha(s)"
  exit 1
fi
echo "mapear: tudo certo"
