# Observação pública de mudanças

`jangada-agentes --observacao-json` informa caminhos absolutos para a Central
acompanhar mudanças com `QFileSystemWatcher`. A resposta é
`{"versao":1,"caminhos":[]}`. Os caminhos são referências opacas para o
Shell; somente o Core seleciona e percorre as áreas de estado.

## Seleção

O Core observa as pastas de sessões, revisões e projetos da fila. Inclui
arquivos JSON e SQLite diretamente nessas pastas, pastas de cada projeto e
arquivos SQLite dentro delas. Pastas e arquivos simbólicos não são percorridos.
Quando uma área ainda não existe, a resposta inclui o antepassado existente
mais próximo para detectar sua criação. Uma consulta sem estado não cria
pastas nem arquivos. Estado ausente, portanto, produz uma lista de
antepassados, que será recalculada no próximo aviso ou na atualização
periódica.

Falhas ao enumerar as pastas-base de sessões, revisões ou projetos recusam a
consulta. Se um projeto desaparecer ou ficar sem permissão durante a leitura,
ele é omitido nesta resposta e será considerado novamente na próxima consulta.
Nomes com caracteres de controle e caminhos acima do limite são omitidos. O
limite total de caminhos ou da resposta continua sendo uma falha explícita.

## Limites e falhas

O envelope da versão 1 exige `versao` inteiro e `caminhos` como lista de
caminhos absolutos, únicos, sem caracteres de controle e com até 4.096
caracteres cada. São aceitos até 4.096 caminhos e 1 MiB de resposta. Erro de
leitura de base, volume excedido, JSON inválido ou versão
desconhecida recusa a resposta inteira com código diferente de zero e
diagnóstico em `stderr`.

A Central consulta o contrato de modo assíncrono, com prazo máximo de um
segundo. Erro ou prazo excedido preserva a lista de observação anterior,
mostra o erro e mantém a atualização periódica a cada 30 segundos. A consulta
de sessões continua separada e aplica seus próprios limites. O Shell não lê
arquivos JSON, bancos SQLite nem monta nomes ou pastas internas.

## Entrega de avisos

Mudanças observadas invalidam os dados exibidos e iniciam uma consulta. Os
avisos próximos são agrupados por 200 ms, com prazo máximo de um segundo para
atualizar apesar de novos eventos. O sistema de arquivos pode perder avisos,
remover temporariamente um caminho observado ou recusar novos caminhos. A
observação não é um registro de eventos e não garante a entrega de toda
mudança. A atualização periódica reserva a recuperação dessas perdas.

O contrato expõe somente caminhos para observação. Não autoriza comandos,
operações nem acesso a outros dados. Uma mudança de armazenamento do Core
exige atualizar a seleção desta consulta, sem alterar a Central.
