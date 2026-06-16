import socket
import json
import logging

class RendezvousClient:
    def __init__(self, server_ip="45.171.101.167", server_port=8080):
        self.server_ip = server_ip
        self.server_port = server_port
        self.logger = logging.getLogger("Rendezvous")

    def _send_request(self, payload: dict) -> dict:
        """
        Abre conexão TCP, envia o comando JSON, recebe a resposta e fecha.
        """
        # Converte o dicionário para string JSON e adiciona a quebra de linha exigida
        message = json.dumps(payload) + "\n"
        
        try:
            # socket.create_connection já lida com a criação e o connect()
            with socket.create_connection((self.server_ip, self.server_port), timeout=5) as sock:
                self.logger.debug(f"Enviando para Rendezvous: {message.strip()}")
                sock.sendall(message.encode('utf-8'))
                
                # Recebe a resposta (até 32KB segundo o protocolo)
                response_bytes = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_bytes += chunk
                    # Se achou a quebra de linha, a mensagem acabou
                    if b"\n" in response_bytes:
                        break
                
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
        Registra este peer no servidor Rendezvous.
        """
        payload = {
            "type": "REGISTER",
            "namespace": namespace,
            "name": name,
            "port": port,
            "ttl": ttl
        }
        self.logger.info(f"Registrando peer {name}@{namespace} na porta {port}...")
        return self._send_request(payload)

    def discover(self, namespace: str = None):
        """
        Busca peers ativos no servidor Rendezvous.
        Se o namespace for omitido, busca de todos os namespaces.
        Retorna uma lista de dicionários com os dados dos peers.
        """
        payload = {"type": "DISCOVER"}
        if namespace:
            payload["namespace"] = namespace
            
        self.logger.info(f"Buscando peers no namespace: {namespace or 'TODOS'}...")
        response = self._send_request(payload)
        
        if response.get("status") == "OK":
            peers = response.get("peers", [])
            self.logger.info(f"{len(peers)} peers encontrados.")
            return peers
        else:
            self.logger.error(f"Erro no Discover: {response.get('message', response)}")
            return []

    def unregister(self, namespace: str, name: str, port: int):
        """
        Remove o registro do peer no servidor (opcional na saída).
        """
        payload = {
            "type": "UNREGISTER",
            "namespace": namespace,
            "name": name,
            "port": port
        }
        self.logger.info(f"Removendo registro do peer {name}@{namespace}...")
        return self._send_request(payload)
    

