import argparse
import json
import threading
import socket
import logging
import time
from datetime import datetime
from packets.controlpacket import ControlPacket
from utils.tree_entry import TreeEntry

class Bootstrapper():
    NEIGHBOURS = 0
    NEIGHBOURS_RESP = 1
    MEASURE = 2
    MEASURE_RESP = 3
    JOIN = 4
    PLAY = 5
    PAUSE = 6
    LEAVE = 7
    STREAM_REQ = 8

    def __init__(self, file):
        with open(file) as f:
            self.nodes = json.load(f)

        self.neighbours = list()

        self.tree_lock = threading.Lock()
        self.tree = dict()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.control_socket.bind(("", 7777))
        self.data_socket.bind(("", 7778))

        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        # Services
        threading.Thread(target=self.pruning_service, args=()).start()
        threading.Thread(target=self.control_service, args=()).start()


    def setup(self):
        my_ip = self.control_socket.gethostbyname(socket.gethostname()) # verificar se isto funciona

        for key, value in self.nodes["nodes"].items():
            if my_ip in value["interfaces"]: # é esse o servidor
                self.database.neighbours = value["neighbours"]


    def neighbours_worker(self, addr):
        neighbours = list()
        servers = list()

        for key, value in self.nodes["nodes"].items():
            if addr[0] in value["interfaces"]: # é esse o servidor
                neighbours = value["neighbours"]

        if addr[0] in self.nodes["rp"]:
            servers = self.nodes["servers"]

        msg = ControlPacket(1, servers=servers, neighbours=neighbours)
        self.control_socket.sendto(msg.serialize(), addr)
        
        self.logger.info(f"Control Service: Message sent to {addr[0]}")
        self.logger.debug(f"Message: {msg}")

    
    def control_worker(self, address, message):
        if message.type == self.JOIN:
            if message.flag == 0:
                message.hops.append(address[0])

                actual_timestamp = float(datetime.now().timestamp())
                latency = actual_timestamp - message.latency
                client = message.source_ip
                neighbour = address[0]

                self.tree_lock.acquire()
                
                if client in self.tree:
                    entry = self.tree[client]
                    
                    if latency < entry.latency:
                        self.logger.debug(f"Control Service: Changing from neighbour {entry.next_step} to neighbour {neighbour}")
                        self.tree[client] = TreeEntry(message.latency, neighbour, actual_timestamp)
                else:
                    self.logger.debug(f"Control Service: Adding neighbour {neighbour} to tree")
                    self.tree[client] = TreeEntry(message.latency, neighbour, actual_timestamp)

                self.tree[client].timestamp = actual_timestamp

                self.tree_lock.release()

                for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                    if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                        self.control_socket.sendto(message.serialize(), (neighbour, 7777))
                        self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {message}")
                        
        
        elif message.type == self.LEAVE:
            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()
        
        elif message.type == self.NEIGHBOURS:
            neighbours = list()
            servers = list()

            for key, value in self.nodes["nodes"].items():
                if address[0] in value["interfaces"]: # é esse o servidor
                    neighbours = value["neighbours"]

            if address[0] in self.nodes["rp"]:
                servers = self.nodes["servers"]

            msg = ControlPacket(1, servers=servers, neighbours=neighbours)
            self.control_socket.sendto(msg.serialize(), address)
            
            self.logger.info(f"Control Service: Message sent to {address[0]}")
            self.logger.debug(f"Message: {msg}")


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                data, address = self.control_socket.recvfrom(1024)
                message = ControlPacket.deserialize(data)

                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {message}")

                threading.Thread(target=self.control_worker, args=(address, message,)).start()

        finally:
            self.control_socket.close()


    def pruning_service(self):
        wait = 20 # 20 segundos
        while True:
            timestamp = float(datetime.now().timestamp())
            
            self.tree_lock.acquire()

            to_remove = list()

            for key, value in self.tree.items():
                if timestamp - value.timestamp >= wait:
                    to_remove.append(key)

                    self.logger.debug(f"Pruning Service: Client {key} was removed from tree")
            
            for key in to_remove:
                self.tree.pop(key)

            self.tree_lock.release()

            time.sleep(wait)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-file", help="bootstrapper file")
    args = parser.parse_args()

    if args.file:
        Bootstrapper(args.file)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
