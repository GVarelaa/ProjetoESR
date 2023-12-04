class NodeInfo:
    def __init__(self, child, child_seqnum, parent=None, parent_seqnum=None):
        self.child = child
        self.child_seqnum = child_seqnum
        self.parent = parent
        self.parent_seqnum = parent_seqnum
    
    def __str__(self):
        return f"Child : {self.child} | Child Sequence Number : {self.child_seqnum} | Parent : {self.parent} | Parent Sequence Number : {self.parent_seqnum}"

    def __repr__(self):
        return f"Child : {self.child} | Child Sequence Number : {self.child_seqnum} | Parent : {self.parent} | Parent Sequence Number : {self.parent_seqnum}"