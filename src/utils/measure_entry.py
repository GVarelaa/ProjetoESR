class MeasureEntry:
    def __init__(self, delay, loss, content):
        self.delay = delay
        self.loss = loss
        self.content = content
    
    def __str__(self):
        return f"Delay : {self.delay} | Loss : {self.loss}"

    def __repr__(self):
        return f"Delay : {self.delay} | Loss : {self.loss}"