class MeasureEntry:
    def __init__(self, delay, loss):
        self.delay = delay
        self.loss = loss
    
    def __str__(self):
        return f"Delay : {self.delay} | Loss : {self.loss}"

    def __repr__(self):
        return f"Delay : {self.delay} | Loss : {self.loss}"