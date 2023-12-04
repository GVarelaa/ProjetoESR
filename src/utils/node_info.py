class NodeInfo:
    def __init__(self, address, delay, loss):
        self.address = address
        self.delay = delay
        self.loss = loss
    
    def __str__(self):
        return f"Address : {self.address} | Delay : {self.delay} | Loss : {self.loss}"

    def __repr__(self):
        return f"Address : {self.address} | Delay : {self.delay} | Loss : {self.loss}"