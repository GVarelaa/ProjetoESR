class NodeInfo:
    def __init__(self, nextstep, seqnum):
        self.nextstep = nextstep
        self.seqnum = seqnum
    
    def __str__(self):
        return f"Next Step : {self.nextstep} | Sequence Number : {self.seqnum}"

    def __repr__(self):
        return f"Next Step : {self.nextstep} | Sequence Number : {self.seqnum}"