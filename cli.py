import threading
import logging
import os
import signal

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

class CLI:
    def __init__(self, peer_table, router, client):
        self.peer_table = peer_table
        self.router = router
        self.client = client
        self.logger = logging.getLogger("CLI")
        self.running = False

    def start(self):
        """Inicia a thread de interface com o utilizador."""
        self.running = True
        
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
        """Interpreta os comandos escritos pelo utilizador."""
        text = text.strip()
        if not text:
            return

        # Divide o comando em no máximo 3 partes (comando, alvo, resto)
        parts = text.split(" ", 2)
        cmd = parts[0].lower()

        if cmd == "/quit":
            self.logger.info("Comando /quit recebido. A encerrar aplicação...")
            # Envia um sinal interno para a thread principal do main fechar tudo
            os.kill(os.getpid(), signal.SIGINT)

        # --- NOVO: /peers com filtros ---
        elif cmd == "/peers":
            filtro = parts[1] if len(parts) > 1 else "*"
            peers = self.peer_table.get_all()
            print(f"\n--- Tabela de Peers (Filtro: {filtro}) ---")
            for pid, dados in peers.items():
                # Se for "*", mostra todos. Se começar com "#", filtra pelo namespace.
                if filtro == "*" or (filtro.startswith("#") and pid.endswith(f"@{filtro[1:]}")):
                    print(f"[{dados['status']}] {pid} - {dados['ip']}:{dados['port']}")
            print("------------------------------------\n")

        # --- NOVO: /rtt ---
        elif cmd == "/rtt":
            peers = self.peer_table.get_all()
            print("\n--- RTT Médio dos Peers ---")
            for pid, dados in peers.items():
                if pid != self.router.my_peer_id: # Ignora a si mesmo
                    avg_rtt = self.peer_table.get_avg_rtt(pid)
                    if avg_rtt > 0:
                        print(f"{pid}: {avg_rtt:.2f} ms")
                    else:
                        print(f"{pid}: N/A (sem medições suficientes)")
            print("---------------------------\n")

        # --- NOVO: /reconnect ---
        elif cmd == "/reconnect":
            print("\n--- Forçando Reconexão Manual ---")
            peers = self.peer_table.get_all()
            for pid, dados in peers.items():
                # Tenta conectar em todos que não são você mesmo e que não estão na lista de conexões ativas
                if pid != self.router.my_peer_id and pid not in self.client.connections:
                    print(f"Tentando reconectar a {pid}...")
                    self.client.connect_to_peer(pid, dados["ip"], dados["port"])
            print("Comandos de conexão disparados!\n")

        # --- NOVO: /log <nível> ---
        elif cmd == "/log":
            if len(parts) > 1:
                nivel_str = parts[1].upper()
                niveis_validos = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                if nivel_str in niveis_validos:
                    novo_nivel = getattr(logging, nivel_str)
                    # Altera o nível do logger global do Python
                    logging.getLogger().setLevel(novo_nivel)
                    for handler in logging.getLogger().handlers:
                        handler.setLevel(novo_nivel)
                    print(f"✓ Nível de log alterado com sucesso para {nivel_str}.")
                else:
                    print(f"⚠️ Nível inválido. Escolha entre: {', '.join(niveis_validos)}")
            else:
                print("⚠️ Uso incorreto. Tente: /log <DEBUG|INFO|WARNING|ERROR|CRITICAL>")

        elif cmd == "/conn":
            conns = self.client.connections
            print("\n--- Conexões TCP Ativas ---")
            if not conns:
                print("Nenhuma ligação ativa neste momento.")
            for pid, conn in conns.items():
                direcao = "Inbound" if conn.is_inbound else "Outbound"
                print(f"[{direcao}] {pid}")
            print("---------------------------\n")

        elif cmd == "/msg":
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
            print("⚠️ Comando desconhecido. Comandos disponíveis:")
            print("   /msg <peer_id> <mensagem>")
            print("   /pub * <mensagem>")
            print("   /pub #<namespace> <mensagem>")
            print("   /peers [* | #namespace]")
            print("   /conn")
            print("   /rtt")
            print("   /reconnect")
            print("   /log <Nível>")
            print("   /quit")

    def _run_prompt_toolkit(self):
        """Loop de interface avançada que protege a zona de input contra quebras de ecrã."""
        session = PromptSession()
        while self.running:
            try:
                # O patch_stdout gere os logs de forma mágica para não destruírem a escrita
                with patch_stdout():
                    text = session.prompt('Você > ')
                self._process_command(text)
            except (KeyboardInterrupt, EOFError):
                self._process_command("/quit")
                break

    def _run_basic(self):
        """Loop de interface básico usando o input() nativo."""
        while self.running:
            try:
                text = input('Você > ')
                self._process_command(text)
            except (KeyboardInterrupt, EOFError):
                self._process_command("/quit")
                break