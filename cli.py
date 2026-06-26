import threading
import logging
import os
import signal

# Tenta importar uma biblioteca avançada para interfaces de terminal.
# O bloco try/except garante que o programa não quebre se o usuário não tiver instalado.
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

class CLI:
    """
    Command Line Interface (CLI).
    Traduz o que o usuário digita no terminal em ações reais do sistema P2P.
    """
    def __init__(self, peer_table, router, client):
        # A CLI precisa ter acesso a tudo para poder comandar o sistema
        self.peer_table = peer_table # Para ver quem está online (comandos /peers, /rtt)
        self.router = router         # Para enviar mensagens (comandos /msg, /pub)
        self.client = client         # Para gerenciar as conexões TCP (comandos /conn, /reconnect)
        
        self.logger = logging.getLogger("CLI")
        self.running = False

    def start(self):
        """Inicia a thread de interface com o utilizador."""
        self.running = True
        
        # Inicia a interface em uma Thread separada. 
        # Isso permite que você digite comandos enquanto o servidor escuta mensagens de rede ao mesmo tempo.
        if PROMPT_TOOLKIT_AVAILABLE:
            self.logger.info("Iniciando CLI avançada com prompt_toolkit...")
            thread = threading.Thread(target=self._run_prompt_toolkit, daemon=True)
        else:
            self.logger.warning(
                "A biblioteca 'prompt_toolkit' não está instalada. "
                "Iniciando CLI básica (logs podem sobrepor a escrita). "
                "Para melhor experiência: pip install prompt_toolkit"
            )
            thread = threading.Thread(target=self._run_basic, daemon=True)
            
        thread.start()

    def _process_command(self, text):
        """
        O 'Cérebro' da interface. Pega o texto bruto e decide o que fazer.
        Atua como um grande roteador de comandos.
        """
        text = text.strip()
        if not text:
            return

        # Divide o comando em no máximo 3 partes para facilitar a leitura.
        # Ex: "/msg kallebe Olá, tudo bem?" vira ["/msg", "kallebe", "Olá, tudo bem?"]
        parts = text.split(" ", 2)
        cmd = parts[0].lower()

        # --- Comandos de Sistema ---
        if cmd == "/quit":
            self.logger.info("Comando /quit recebido. A encerrar aplicação...")
            # Envia um sinal (SIGINT - como se fosse um Ctrl+C) para o sistema operacional matar o processo graciosamente.
            os.kill(os.getpid(), signal.SIGINT)

        # --- Comandos de Visualização de Rede ---
        elif cmd == "/peers":
            # Lista quem está registrado na "lista telefônica"
            filtro = parts[1] if len(parts) > 1 else "*"
            peers = self.peer_table.get_all()
            print(f"\n--- Tabela de Peers (Filtro: {filtro}) ---")
            for pid, dados in peers.items():
                if filtro == "*" or (filtro.startswith("#") and pid.endswith(f"@{filtro[1:]}")):
                    print(f"[{dados['status']}] {pid} - {dados['ip']}:{dados['port']}")
            print("------------------------------------\n")

        elif cmd == "/rtt":
            # Exibe a latência (Round Trip Time) que foi calculada lá pelo PING/PONG
            peers = self.peer_table.get_all()
            print("\n--- RTT Médio dos Peers ---")
            for pid, dados in peers.items():
                if pid != self.router.my_peer_id: 
                    avg_rtt = self.peer_table.get_avg_rtt(pid)
                    if avg_rtt > 0:
                        print(f"{pid}: {avg_rtt:.2f} ms")
                    else:
                        print(f"{pid}: N/A (sem medições suficientes)")
            print("---------------------------\n")

        elif cmd == "/reconnect":
            # Força o sistema a tentar se ligar ativamente a todos os peers conhecidos
            print("\n--- Forçando Reconexão Manual ---")
            peers = self.peer_table.get_all()
            for pid, dados in peers.items():
                if pid != self.router.my_peer_id and pid not in self.client.connections:
                    print(f"Tentando reconectar a {pid}...")
                    self.client.connect_to_peer(pid, dados["ip"], dados["port"])
            print("Comandos de conexão disparados!\n")

        elif cmd == "/log":
            # Altera o nível de detalhe do que aparece na tela em tempo real
            # Útil para debugar o sistema sem precisar reiniciar
            if len(parts) > 1:
                nivel_str = parts[1].upper()
                niveis_validos = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                if nivel_str in niveis_validos:
                    novo_nivel = getattr(logging, nivel_str)
                    logging.getLogger().setLevel(novo_nivel)
                    for handler in logging.getLogger().handlers:
                        handler.setLevel(novo_nivel)
                    print(f"✓ Nível de log alterado com sucesso para {nivel_str}.")
                else:
                    print(f"⚠️ Nível inválido. Escolha entre: {', '.join(niveis_validos)}")
            else:
                print("⚠️ Uso incorreto. Tente: /log <DEBUG|INFO|WARNING|ERROR|CRITICAL>")

        elif cmd == "/conn":
            # Mostra quem está fisicamente conectado via TCP agora
            conns = self.client.connections
            print("\n--- Conexões TCP Ativas ---")
            if not conns:
                print("Nenhuma ligação ativa neste momento.")
            for pid, conn in conns.items():
                direcao = "Inbound" if conn.is_inbound else "Outbound"
                print(f"[{direcao}] {pid}")
            print("---------------------------\n")

        # --- Comandos de Ação (Mensagens) ---
        elif cmd == "/msg":
            # Manda para o 'MessageRouter' fazer o envio Unicast
            if len(parts) < 3:
                print("⚠️ Uso incorreto. Tente: /msg <peer_id> <sua mensagem>")
            else:
                peer_id = parts[1]
                mensagem = parts[2]
                sucesso = self.router.send_direct(peer_id, mensagem)
                if sucesso:
                    print(f"✓ Mensagem enviada para {peer_id}.")
                else:
                    print(f"❌ Erro: Não existe uma ligação ativa com {peer_id}.")

        elif cmd == "/pub":
            # Manda para o 'MessageRouter' fazer o envio Multicast/Broadcast
            if len(parts) < 3:
                print("⚠️ Uso incorreto. Tente: /pub * <msg> OU /pub #<namespace> <msg>")
            else:
                alvo = parts[1]
                mensagem = parts[2]
                
                if alvo == "*":
                    self.router.publish_global(mensagem)
                    print("✓ [PUB Global] Mensagem enviada para todos.")
                elif alvo.startswith("#"):
                    ns = alvo[1:]
                    self.router.publish_namespace(ns, mensagem)
                    print(f"✓ [PUB #{ns}] Mensagem enviada para o namespace {ns}.")
                else:
                    print("⚠️ Destino inválido para /pub. Use '*' ou '#namespace'.")
        else:
            # Menu de Ajuda (Fallback)
            print("⚠️ Comando desconhecido. Comandos disponíveis:")
            # ... (prints de ajuda omitidos na leitura para economizar tempo)

    # --- Loops de Interface ---
    
    def _run_prompt_toolkit(self):
        """Loop de interface avançada que protege a zona de input contra quebras de ecrã."""
        session = PromptSession()
        while self.running:
            try:
                # O patch_stdout cria uma 'camada' por cima da tela. 
                # Se uma mensagem de log ou de chat chegar enquanto o usuário digita, 
                # ela é impressa acima da linha de input, sem apagar o que já foi digitado!
                with patch_stdout():
                    text = session.prompt('Você > ')
                self._process_command(text)
            except (KeyboardInterrupt, EOFError):
                self._process_command("/quit")
                break

    def _run_basic(self):
        """Loop de interface básico usando o input() nativo do Python."""
        while self.running:
            try:
                # Funciona, mas se chegar um print() de outra thread,
                # ele corta a palavra "Você > " no meio e bagunça o terminal.
                text = input('Você > ')
                self._process_command(text)
            except (KeyboardInterrupt, EOFError):
                self._process_command("/quit")
                break