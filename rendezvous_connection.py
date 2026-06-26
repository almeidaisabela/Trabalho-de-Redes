import socket
import json
import logging

class RendezvousClient:
    """
    Cliente para conversar com o servidor central (Rendezvous).
    Atua como a "lista telefônica" do sistema, permitindo que os peers se encontrem.
    """
    def __init__(self, server_ip="45.171.101.167", server_port=8080):
        # Endereço IP e porta do servidor central público
        self.server_ip = server_ip
        self.server_port = server_port
        self.logger = logging.getLogger("Rendezvous")

    def _send_request(self, payload: dict) -> dict:
        """
        Concentra todo o trabalho de rede: abre a conexão TCP, envia o JSON, 
        espera a resposta acabar e fecha tudo.
        """
        # O protocolo do servidor exige que toda mensagem seja um JSON que termina com '\n'
        message = json.dumps(payload) + "\n"
        
        try:
            # socket.create_connection já cria e conecta. 
            # O timeout=5 evita que o programa congele para sempre se a internet cair.
            with socket.create_connection((self.server_ip, self.server_port), timeout=5) as sock:
                self.logger.debug(f"Enviando para Rendezvous: {message.strip()}")
                sock.sendall(message.encode('utf-8'))
                
                # O TCP não garante entregar tudo de uma vez. Recebemos em blocos (chunks).
                response_bytes = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk: # Servidor fechou a conexão
                        break
                    response_bytes += chunk
                    
                    # O delimitador '\n' avisa que a mensagem inteira já chegou
                    if b"\n" in response_bytes:
                        break
                
                # Transforma os bytes recebidos de volta em dicionário Python
                response_text = response_bytes.decode('utf-8').strip()
                self.logger.debug(f"Resposta do Rendezvous: {response_text}")
                
                if response_text:
                    return json.loads(response_text)
                return {}
                
        except Exception as e:
            self.logger.error(f"Erro na comunicação com o Rendezvous: {e}")
            return {"status": "ERROR", "message": str(e)}

    def register(self, namespace: str, name: str, port: int, ttl: int = 7200):
        """
        Avisa ao servidor central: "Estou online, este é meu nome, sala e porta".
        """
        payload = {
            "type": "REGISTER",
            "namespace": namespace, # Ex: RedesUnB (a sala)
            "name": name,           # Ex: kallebe (você)
            "port": port,
            "ttl": ttl              # Time-to-Live: Tempo em segundos (2h) para o servidor expirar seu nome se você sumir
        }
        self.logger.info(f"Registrando peer {name}@{namespace} na porta {port}...")
        return self._send_request(payload)

    def discover(self, namespace: str = None):
        """
        Pede ao servidor central a lista de IPs de quem já está conectado.
        """
        payload = {"type": "DISCOVER"}
        
        # Se passar o namespace, o servidor filtra e devolve só a galera daquela "sala"
        if namespace:
            payload["namespace"] = namespace
            
        self.logger.info(f"Buscando peers no namespace: {namespace or 'TODOS'}...")
        response = self._send_request(payload)
        
        # Se a requisição deu certo, extrai apenas a lista de peers
        if response.get("status") == "OK":
            peers = response.get("peers", [])
            self.logger.info(f"{len(peers)} peers encontrados.")
            return peers
        else:
            self.logger.error(f"Erro no Discover: {response.get('message', response)}")
            return []

    def unregister(self, namespace: str, name: str, port: int):
        """
        Boa prática: Descadastro. Quando apertamos Ctrl+C, o programa avisa 
        ao servidor central para tirar nosso IP da lista telefônica.
        """
        payload = {
            "type": "UNREGISTER",
            "namespace": namespace,
            "name": name,
            "port": port
        }
        self.logger.info(f"Removendo registro do peer {name}@{namespace}...")
        return self._send_request(payload)