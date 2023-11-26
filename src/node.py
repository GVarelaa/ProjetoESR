import argparse
import json
import time
import socket
import threading
import logging
from datetime import datetime
from packets.control_packet import ControlPacket
from utils.measure_entry import MeasureEntry
from abc import abstractmethod
from math import inf

class Node:
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None, debug_mode=False):
        self.is_bootstrapper = is_bootstrapper
        if is_bootstrapper:
            with open(file) as f:
                self.nodes = json.load(f)

        self.neighbours = list()
        self.streams = list()

        self.contents = dict()
        self.tree = dict()
        self.tree_lock = threading.Lock()

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(("", 7777))
        
        address = bootstrapper.split(":")
        self.bootstrapper = (address[0], int(address[1]))

        if debug_mode:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

        self.logger = logging.getLogger()
        self.logger.info("Control service listening on port 7777 and streaming service on port 7778")

        self.setup() # Request neighbours

        # Services
        #threading.Thread(target=self.pruning_service, args=()).start()
        threading.Thread(target=self.control_service, args=()).start()
        threading.Thread(target=self.measure_service, args=()).start()
        

    @abstractmethod
    def setup(self):
        if self.is_bootstrapper:
            for key, value in self.nodes["nodes"].items():
                if self.bootstrapper in value["interfaces"]: # é esse o servidor
                    self.neighbours = value["neighbours"]

        else:
            self.control_socket.sendto(ControlPacket(ControlPacket.NEIGHBOURS).serialize(), self.bootstrapper)
            self.logger.info("Setup: Asked for neighbours")

            try:
                self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

                data, _ = self.control_socket.recvfrom(1024)
                msg = ControlPacket.deserialize(data)

                if msg.type == ControlPacket.NEIGHBOURS and msg.response == 1:
                    self.neighbours = msg.neighbours
                    self.logger.info("Setup: Neighbours received")
                    self.logger.debug(f"Neighbours: {self.neighbours}")
                
                else:
                    self.logger.info("Setup: Unexpected response received")
                    exit() # É este o comportamento que queremos ?
                
            except socket.timeout:
                self.logger.info("Setup: Could not receive response to neighbours request")
                exit()
    

    def insert_tree(self, message, address):
        client = message.source_ip
        neighbour = address[0]
        content = message.contents[0]

        self.tree_lock.acquire()

        if client in self.tree:
            self.tree[client][neighbour] = None

        else:
            self.tree[client] = dict()
            self.tree[client][neighbour] = None

            if content not in self.contents:
                self.contents[content] = list()

            self.contents[content].append(client)

            self.logger.debug(f"Control Service: Added client {client} to tree")

        self.tree_lock.release()


    @abstractmethod
    def control_worker(self, address, msg):
        if self.is_bootstrapper and msg.type == ControlPacket.NEIGHBOURS and msg.response == 0:
            neighbours = list()
            servers = list()

            for key, value in self.nodes["nodes"].items():
                if address[0] in value["interfaces"]: # é esse o servidor
                    neighbours = value["neighbours"]

            if address[0] in self.nodes["rp"]:
                servers = self.nodes["servers"]

            msg = ControlPacket(ControlPacket.NEIGHBOURS, response=1, servers=servers, neighbours=neighbours)
            self.control_socket.sendto(msg.serialize(), address)
            
            self.logger.info(f"Control Service: Message sent to {address[0]}")
            self.logger.debug(f"Message: {msg}")

        elif msg.type == ControlPacket.PLAY:
            if msg.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                msg.last_hop = address[0]

                if msg.source_ip == "0.0.0.0":
                    msg.source_ip = address[0]

                self.insert_tree(msg, address)

                if not msg.contents[0] in self.streams: # Se o nodo atual nao estiver a streamar o content pedido então faz flood
                    for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                        if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                            self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                            self.logger.debug(f"Message sent: {msg}")

            elif msg.response == 1:
                # ABRIR O SOCKET COM A PORTA PASSADA PRA RECEBER A STREAM E CRIAR THREAD PRA LISTEN
                # LANÇAMOS AQUI UMA THREAD PARA RECEBER A STREAM?

                for neighbour in self.neighbours:
                    if neighbour != address[0]:
                        self.control_socket.sendto(ControlPacket(ControlPacket.PLAY, response=1, port=msg.port, contents=[msg.contents[0]]).serialize(), (neighbour, 7777))
                        self.logger.info(f"Control Service: Port messaage sent to neighbour {neighbour}")
                        self.logger.debug(f"Message sent: {msg}")
                
                threading.Thread(target=self.listen_rtp, args=(msg.port, msg.contents[0])).start()

        
        elif msg.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()
        elif msg.type == ControlPacket.MEASURE:
            # TER CUIDADO COM AS INTERFACES
            self.tree_lock.acquire()

            for client in self.tree:
                if address[0] in self.tree[client]:
                    delay = float(datetime.now().timestamp()) - msg.timestamp# delay ou latencia que se chama?
                    self.tree[client][address[0]] = MeasureEntry(delay, 0) # FAZER O LOSS

            self.tree_lock.release()


    def control_service(self):
        try:
            self.control_socket.settimeout(None)

            while True:
                data, address = self.control_socket.recvfrom(1024)
                message = ControlPacket.deserialize(data)

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

    
    def measure_service(self):
        wait = 5
        while True:
            for neighbour in self.neighbours:
                message = ControlPacket(ControlPacket.MEASURE)
                self.control_socket.sendto(message.serialize(), (neighbour, 7777))
            
            self.logger.info(f"Measure Service: Monitorization messages sent to {self.neighbours}")

            time.sleep(wait)


    def listen_rtp(self, port, content):
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_socket.bind(("", port))

        self.logger.info(f"Streaming Service: Receiving RTP Packets")

        try:
            while True:
                data, _ = data_socket.recvfrom(20480)

                clients = self.contents[content]

                steps = set()
                for client in clients:
                    best_step = None

                    self.tree_lock.acquire()
                    for step, measure in self.tree[client].items():
                        if measure is not None and best_step is not None:
                            if best_step[1] > measure.delay:
                                best_step = (step, measure.delay)
                        elif measure is not None:
                            best_step = (step, measure.delay)
                        else:
                            best_step = (step, inf)
                    steps.add(best_step[0])
                    self.tree_lock.release()

                for step in steps:
                    data_socket.sendto(data, (step, port))
                    self.logger.debug(f"Streaming Service: RTP Packet sent to {step}")
        
        finally:
            data_socket.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-bootstrapper", help="bootstrapper ip")
    parser.add_argument("-file", help="bootstrapper file")
    parser.add_argument("-d", action="store_true", help="activate debug mode")
    args = parser.parse_args()

    debug_mode = False

    if args.d:
        debug_mode = True

    if args.file:
        Node(args.bootstrapper, is_bootstrapper=True, file=args.file, debug_mode=debug_mode)
        
    elif args.bootstrapper:
        Node(args.bootstrapper, debug_mode=debug_mode)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()