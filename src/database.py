import threading
from datetime import datetime
from entry import Entry
from server_info import ServerInfo

class Database:
    def __init__(self, logger):
        self.neighbours = list()

        # READ WRITE LOCK ?
        self.tree_lock = threading.Lock()
        self.tree = dict()

        self.servers_lock = threading.Lock()
        self.servers = dict()

        self.logger = logger


    def insert_servers(self, source_ip, timestamp, contents):
        actual_timestamp = float(datetime.now().timestamp())
        latency = actual_timestamp - timestamp

        self.servers_lock.acquire()

        self.servers[source_ip] = ServerInfo(source_ip, latency, contents, True) 

        self.servers_lock.release()


    def insert_tree(self, client, neighbour, timestamp):
        actual_timestamp = float(datetime.now().timestamp())
        latency = actual_timestamp - timestamp

        self.tree_lock.acquire()
        
        if client in self.tree:
            entry = self.tree[client]
            
            if latency < entry.latency:
                self.logger.debug(f"Control Service: Changing from neighbour {entry.next_step} to neighbour {neighbour}")
                self.tree[client] = Entry(timestamp, neighbour, latency)
        else:
            self.logger.debug(f"Control Service: Adding neighbour {neighbour}")
            self.tree[client] = Entry(timestamp, neighbour, latency)

        self.tree[client].timestamp = actual_timestamp

        self.tree_lock.release()


    def prune_tree(self, timestamp, wait_time):
        self.tree_lock.acquire()

        to_remove = list()

        for key, value in self.tree.items():
            if timestamp - value.timestamp >= wait_time:
                to_remove.append(key)

                self.logger.debug(f"Pruning Service: Client {key} was removed from tree")
        
        for key in to_remove:
            self.tree.pop(key)

        self.tree_lock.release()

    
    def remove_tree(self, addr):
        self.tree_lock.acquire()

        if addr in self.tree:
            self.tree.pop(addr)

        self.logger.debug(f"Control Service: Client {addr} was removed from tree")

        self.tree_lock.release()