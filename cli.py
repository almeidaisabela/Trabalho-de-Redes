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

        parts = text.split(" ", 2)
        cmd = parts[0].lower()

        if cmd == "/quit":
            self.logger.info("Comando /quit recebido. A encerrar aplicação...")
            # Envia um sinal (Ctrl+C) interno para a thread principal do main fechar tudo de forma limpa
            os.kill(os.getpid(), signal.SIGINT)

        elif cmd == "/peers":
            peers = self.peer_table.get_all()
            print("\n--- Tabela de Peers (Conhecidos) ---")
            for pid, dados in peers.items():
                print(f"[{dados['status']}] {pid} - {dados['ip']}:{dados['port']}")
            print("------------------------------------\n")

        elif cmd == "/conn":
            conns = self.client.connections
            print("\n--- Conexões TCP Ativas ---")
            if not conns:
                print("Nenhuma ligação ativa neste momento.")
            for pid, conn in conns.items():
                direcao = "Inbound" se conn.is_inbound else "Outbound"
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
            print("   /peers")
            print("   /conn")
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