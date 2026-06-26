# Chat P2P - Redes de Computadores 🌐

Projeto final desenvolvido para a disciplina de Redes de Computadores. Trata-se de um cliente de Chat *Peer-to-Peer* (P2P) descentralizado, com suporte a mensagens diretas, broadcast em namespaces e mecanismo de resiliência (Keep-Alive).

## Equipa (Grupo 07)
* **Arthur Martins Pereira de Souza** - Matrícula: 241004499
* **Isabela [Sobrenome da Isabela]** - Matrícula: [000000000]
* **Rian Kallebe da Silva Lisbôa** - Matrícula: 242012000

## Arquitetura e Funcionalidades
* **Rendezvous:** Registo e descoberta automática de nós na rede.
* **Handshake P2P:** Ligação direta TCP entre clientes com troca de `HELLO` e `HELLO_OK`.
* **Roteamento:** Suporte a mensagens diretas (`SEND`/`ACK`) e difusão em grupo (`PUB`).
* **Keep-Alive:** Pings automáticos a cada 30 segundos para monitorizar a saúde da rede e calcular o RTT médio.
* **Backoff Exponencial:** Mecanismo dinâmico de reconexão automática caso um nó caia.
* **CLI Avançada:** Interface de linha de comandos protegida contra sobreposição de logs.

## Como Executar

### 1. Requisitos
* Linux (Ubuntu ou similar recomendado)
* Python 3.8 ou superior

### 2. Instalação das Dependências
A aplicação utiliza a biblioteca `prompt_toolkit` para garantir uma interface de terminal fluida. Instale-a executando:
```bash
pip install prompt_toolkit

```

### 3. Execução

Execute o ficheiro principal passando o seu nome e a porta TCP desejada:

```bash
python3 main.py <seu_nome> <sua_porta>
# Exemplo: python3 main.py kallebe 4000

```

### Comandos Disponíveis na CLI

A interface de linha de comandos (CLI) permite a interação em tempo real com a rede. Digite os seguintes comandos no terminal:

* **/msg <peer_id> ** — Envia uma mensagem privada de texto para um peer específico (requer uma ligação TCP ativa).
* **/pub * ** — Realiza um envio global (Broadcast), retransmitindo a mensagem para todos os peers conectados.
* **/pub # ** — Envia uma mensagem em grupo exclusivamente para os peers que pertencem ao namespace informado.
* **/peers [* | #namespace]** — Exibe a tabela local de utilizadores descobertos. Use `*` para listar todos ou `#nome` para filtrar por grupo.
* **/conn** — Lista detalhadamente todas as ligações TCP atualmente estabelecidas (Inbound e Outbound).
* **/rtt** — Calcula e exibe a latência média (em milissegundos) baseada no histórico dos últimos PINGs/PONGs trocados com cada peer.
* **/reconnect** — Ignora o temporizador de backoff e força uma tentativa imediata de religação a todos os peers conhecidos que estão offline.
* **/log <NÍVEL>** — Ajusta a verbosidade do terminal em tempo real. Opções válidas: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`.
* **/quit** — Encerra a aplicação de forma segura, fechando os sockets, enviando o comando de despedida (`BYE`) e desregistando o nó do Rendezvous.

