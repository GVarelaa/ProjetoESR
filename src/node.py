import argparse
import json
import time
import socket
import threading
import logging
import errno
from datetime import datetime
from packets.control_packet import ControlPacket
from utils.node_info import NodeInfo
from abc import abstractmethod
from math import inf

class Node:
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None, debug_mode=False):
        self.is_bootstrapper = is_bootstrapper
        if is_bootstrapper:
            with open(file) as f:
                self.nodes = json.load(f)

        self.neighbours = list()


        self.streams = dict() # Dicionário -> Conteudo : (Porta, Frame Number)
        self.tree = dict() # {conteudo -> {cliente -> best nodeInfo } }
        self.lock = threading.Lock()

        self.last_contacts = dict() # Guarda o timestamp do último contacto com cada cliente para o pruning
        self.last_contacts_lock = threading.Lock()
        
        self.ports = dict() # estrutura para saber as portas para cada conteudo

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
    

    @abstractmethod
    def insert_tree(self, msg, neighbour):
        client = msg.hops[0]
        content = msg.contents[0]
        seqnum = msg.seqnum

        self.lock.acquire()

        if content not in self.tree:
            self.tree[content] = dict()

        self.tree[content][client] = NodeInfo(neighbour, seqnum)

        self.logger.info(f"Control Service: Added client {client} to tree")

        self.lock.release()


    @abstractmethod
    def control_worker(self, address, msg):
        print(msg)
        print(address[0])
        
        print(self.tree)

        # Se tem ciclos
        if address[0] in msg.hops:
            return
        
        if msg.response == 0:
            msg.hops.append(address[0])
        
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
            if msg.nack == 1:
                client = msg.hops[0]
                content = msg.contents[0]
                
                self.lock.acquire()
                
                try:
                    self.tree[content].pop(client)
                    self.logger.info(f"Control Service: Client {client} removed from tree due to NACK")
                
                except:
                    print("FUCK EXCEÇOES")

                self.lock.release()

                for neighbour in self.neighbours:
                    if neighbour != address[0]:
                        self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                        self.logger.debug(f"Control Service: NACK sent to {neighbour}")


            elif msg.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                self.insert_tree(msg, address[0])

                content = msg.contents[0]
                if not content in self.streams or (content in self.streams and len(self.tree[content].keys()) == 1 and msg.hops[0] in self.tree[content].keys()): # Se o nodo atual nao estiver a streamar o content pedido então faz flood
                    for neighbour in self.neighbours: # Fazer isto sem ser sequencial (cuidado ter um socket para cada neighbour)
                        if neighbour != address[0]: # Se o vizinho não for o que enviou a mensagem
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                            self.logger.info(f"Control Service: Subscription message sent to neighbour {neighbour}")
                            self.logger.debug(f"Message sent: {msg}")
                else:
                    msg.response = 1
                    msg.port = self.ports[msg.contents[0]]
                    
                    self.control_socket.sendto(msg.serialize(), (address[0], 7777))
                    self.logger.info(f"Control Service: Port message sent to neighbour {address[0]}")
                    self.logger.debug(f"Message sent: {msg}")

            elif msg.response == 1:
                self.ports[msg.contents[0]] = msg.port # guardar porta
                # ABRIR O SOCKET COM A PORTA PASSADA PRA RECEBER A STREAM E CRIAR THREAD PRA LISTEN
                # LANÇAMOS AQUI UMA THREAD PARA RECEBER A STREAM?
                seqnum = msg.seqnum
                client = msg.hops[0]
                content = msg.contents[0]

                self.lock.acquire()

                parent_seqnum = self.tree[content][client].parent_seqnum
                if parent_seqnum is None or parent_seqnum < seqnum:
                    self.tree[content][client].parent = address[0]
                    self.tree[content][client].parent_seqnum = seqnum

                    msg.response = 1
                    self.control_socket.sendto(msg.serialize(), (self.tree[content][client].child, 7777))
                    self.logger.info(f"Control Service: Port message sent to neighbour {self.tree[content][client].child}")
                    self.logger.debug(f"Message sent: {msg}")

                    for neighbour in self.neighbours:
                        if neighbour != address[0] and neighbour != client and neighbour not in msg.hops:
                            msg.nack = 1
                            print(msg)
                            self.control_socket.sendto(msg.serialize(), (neighbour, 7777))
                            self.logger.debug(f"Control Service: NACK sent to {neighbour}")

                self.lock.release()
                
                threading.Thread(target=self.listen_rtp, args=(msg.port, msg.contents[0])).start()

        
        elif msg.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            content = msg.contents[0]

            self.lock.acquire()

            if content in self.tree:
                client = msg.hops[0]

                if client in self.tree[content]:
                    next_step = self.tree[content].pop(client)
                    
                    if len(list(self.tree[content].keys())) == 0:
                        
                        try:
                            self.streams.pop(content)
                            self.logger.debug(f"Control Service: Client {client} was removed from tree")

                            self.control_socket.sendto(msg.serialize(), (next_step.parent, 7777))
                            self.logger.info(f"Control Service: Leave message sent to neighbour {next_step.parent}")
                            self.logger.debug(f"Message sent: {msg}")                        
                        except:
                            print("FUCK EXCEÇOES")

            self.lock.release()


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
            to_remove = list()

            self.last_contacts_lock.acquire()

            for client, last_contact in self.last_contacts.items():
                if timestamp - last_contact > 10: # TEMOS DE MUDAR PARA 1 !!!!!!!!!!!!!!!!!!!!!!!!!
                    to_remove.append(client)

            self.last_contacts_lock.release()

            self.lock.acquire()

            for client in to_remove:
                for content, clients in self.tree.items():
                    if client in clients:
                        self.tree[content].pop(client)

                        self.logger.info(f"Pruning Service: Client {client} was removed from tree")

                        if len(list(self.tree[content].keys())) == 0:
                            self.streams.pop(content)
            
            self.lock.release()

            time.sleep(wait)


    def listen_rtp(self, port, content):
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        try:
            data_socket.bind(("", port))

            self.logger.info(f"Streaming Service: Receiving RTP Packets")

            while True:
                data, _ = data_socket.recvfrom(20480)

                self.lock.acquire()

                if content not in self.streams:
                    self.streams[content] = 0
                else:
                    self.streams[content] += 1

                steps = set()
                clients = self.tree[content]

                for step in clients.values():
                    steps.add(step)
                    
                self.lock.release()

                for step in steps:
                    data_socket.sendto(data, (step.child, port))
                    self.logger.debug(f"Streaming Service: RTP Packet sent to {step.child}")
            
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:      
                #data_socket.close()
                print("mudar") 

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