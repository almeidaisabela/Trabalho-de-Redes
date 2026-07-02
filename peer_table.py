import json
import os

class PeerTable:
    def __init__(self):
        self.peers = {}
        
        # --- NOVO: Lê o tamanho da janela de RTT do config.json ---
        self.rtt_window_size = 10
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    config_data = json.load(f)
                    self.rtt_window_size = config_data.get("rtt_window_size", 10)
            except Exception:
                pass

    def update(self, peers):
        """Atualiza a tabela com os peers retornados pelo DISCOVER."""
        for peer in peers:
            peer_id = f"{peer['name']}@{peer['namespace']}"
            
            # Se o peer é novo, cria a estrutura com a lista de histórico vazia
            if peer_id not in self.peers:
                self.peers[peer_id] = {
                    "ip": peer["ip"],
                    "port": peer["port"],
                    "status": "KNOWN",
                    "rtt_history": [] 
                }
            else:
                # Se já existe, atualiza apenas o IP e a Porta caso ele tenha mudado de rede
                self.peers[peer_id]["ip"] = peer["ip"]
                self.peers[peer_id]["port"] = peer["port"]
                # Garante que a lista existe caso falhe algo
                if "rtt_history" not in self.peers[peer_id]:
                    self.peers[peer_id]["rtt_history"] = []

    def get_all(self):
        return self.peers

    def get(self, peer_id):
        return self.peers.get(peer_id)
    
    def update_status(self, peer_id, status):
        if peer_id in self.peers:
            self.peers[peer_id]["status"] = status

    def mark_stale(self, peer_id):
        self.update_status(peer_id, "STALE")

    # --- NOVAS FUNÇÕES DA FASE 4 ---

    def add_rtt(self, peer_id, rtt):
        """Adiciona um novo valor de RTT ao histórico do peer."""
        if peer_id in self.peers:
            historico = self.peers[peer_id].setdefault("rtt_history", [])
            historico.append(rtt)
            
            # Mantém apenas os valores definidos no config.json para a média ser sempre recente
            if len(historico) > self.rtt_window_size:
                historico.pop(0)

    def get_avg_rtt(self, peer_id):
        """Calcula e devolve o RTT médio de um peer específico."""
        if peer_id in self.peers:
            historico = self.peers[peer_id].get("rtt_history", [])
            if historico:
                return sum(historico) / len(historico)
        return 0.0