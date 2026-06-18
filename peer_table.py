class PeerTable:
    def __init__(self):
        self.peers = {}

    def update(self, peers):
        """Atualiza a tabela com os peers retornados pelo DISCOVER."""
        for peer in peers:
            peer_id = f"{peer['name']}@{peer['namespace']}"
            self.peers[peer_id] = {
                "ip": peer["ip"],
                "port": peer["port"],
                "status": "KNOWN"
            }

    def get_all(self):
        return self.peers

    def get(self, peer_id):
        return self.peers.get(peer_id)
    
    def update_status(self, peer_id, status):
        if peer_id in self.peers:
            self.peers[peer_id]["status"] = status

    def mark_stale(self, peer_id):
        self.update_status(peer_id, "STALE")