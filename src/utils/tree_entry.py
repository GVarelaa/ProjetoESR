class TreeEntry:
    def __init__(self, timestamp, next_step, latency):
        self.timestamp = timestamp # Último contacto do cliente
        self.next_step = next_step
        self.latency = latency
    
    def __str__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency}"

    def __repr__(self):
        return f"Next Step: {self.next_step} | Timestamp: {self.timestamp} | Latency Metric: {self.latency}"