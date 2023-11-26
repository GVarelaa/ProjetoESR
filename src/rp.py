import argparse
import json
import threading
import logging
import time
import socket
from datetime import datetime
from node import Node
from packets.control_packet import ControlPacket
from utils.measure_entry import MeasureEntry
from utils.status_entry import StatusEntry

class RP(Node):
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None, debug_mode=False):        
        self.servers = dict()
        self.servers_lock = threading.Lock()

        self.ports = dict() # estrutura para saber as portas para cada conteudo

        self.initial_port = 7778 # a partir daqui incrementa

        super().__init__(bootstrapper, is_bootstrapper=is_bootstrapper, file=file, debug_mode=debug_mode)

        # Services
        threading.Thread(target=self.tracking_service, args=()).start()

    
    def setup(self):
        if self.is_bootstrapper:
            for key, value in self.nodes["nodes"].items():
                if self.bootstrapper in value["interfaces"]: # é esse o servidor
                    self.neighbours = value["neighbours"]
        
        else:
            self.control_socket.sendto(ControlPacket(ControlPacket.NEIGHBOURS).serialize(), self.bootstrapper)
            self.logger.info("Setup: Asked for neighbours and servers")

            try:
                self.control_socket.settimeout(5) # 5 segundos? perguntar ao lost

                data, _ = self.control_socket.recvfrom(1024)
                msg = ControlPacket.deserialize(data)

                if msg.type == ControlPacket.NEIGHBOURS and msg.response == 1:
                    self.neighbours = msg.neighbours

                    for server in msg.servers:
                        self.servers[server] = None
                    
                    self.logger.info("Setup: Neighbours and servers received")
                    self.logger.debug(f"Neighbours: {self.neighbours}")
                    self.logger.debug(f"Servers: {self.servers}")
                
                else:
                    self.logger.info("Setup: Unexpected response received")
                    exit() # É este o comportamento que queremos ?
                
            except socket.timeout:
                self.logger.info("Setup: Could not receive response to neighbours and servers request")
                exit()


    def control_worker(self, address, message):
        if self.is_bootstrapper and message.type == ControlPacket.NEIGHBOURS and message.response == 0:
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
        
        elif message.type == ControlPacket.PLAY:
            if message.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {message}")

                if message.source_ip == "0.0.0.0":
                    message.source_ip = address[0]

                self.insert_tree(message, address) # Enviar para trás (source_ip=cliente)

                content = message.contents[0]
                if content not in self.streams: # Se não está a streamar então vai contactar o melhor servidor com aquele conteudo pra lhe pedir a stream
                    self.streams.append(content)

                    port = None
                    if content in self.ports:
                        port = self.ports[content]
                    else:
                        port = self.initial_port
                        self.ports[content] = port
                        self.initial_port += 1

                    # FAZER FLOOD DA PORTA PROS VIZINHOS?
                    for neighbour in self.neighbours:
                        self.control_socket.sendto(ControlPacket(ControlPacket.PLAY, response=1, port=port, contents=[content]).serialize(), (neighbour, 7777))

                    self.servers_lock.acquire()
                    best_server = None
                    for server, value in self.servers.items():
                        if value is not None and content in value.contents:
                            if best_server is not None:
                                if best_server[1] > value.metric:
                                    best_server = (server, value.metric)
                            else:
                                best_server = (server, value.metric)
                    self.servers_lock.release()

                    self.control_socket.sendto(ControlPacket(ControlPacket.PLAY, port=port, contents=[content]).serialize(), (best_server[0], 7777)) # Proteger para casos em que ainda nao tem best server

                    self.logger.info(f"Control Service: Streaming request sent to server {best_server[0]}")
                    self.logger.debug(f"Message sent: {message}")

                    # LANÇAMOS AQUI UMA THREAD PARA RECEBER A STREAM?
                    threading.Thread(target=self.listen_rtp, args=(port, content)).start()

        
        elif message.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {message}")

            self.tree_lock.acquire()

            if address in self.tree:
                self.tree.pop(address)

            self.logger.debug(f"Control Service: Client {address} was removed from tree")

            self.tree_lock.release()

        elif message.type == ControlPacket.STATUS and message.response == 1:
            self.logger.info(f"Control Service: Status response received from server {address[0]}")
            self.logger.debug(f"Message received: {message}")

            actual_timestamp = float(datetime.now().timestamp())
            latency = actual_timestamp - message.latency

            self.servers_lock.acquire()

            self.servers[address[0]] = StatusEntry(latency, message.contents, True)

            self.logger.info(f"Control Service: Status from {address} was updated")

            self.servers_lock.release()
        
        elif message.type == ControlPacket.MEASURE:
            # TER CUIDADO COM AS INTERFACES
            self.tree_lock.acquire()
            
            for client in self.tree:
                if address[0] in self.tree[client]:
                    delay = float(datetime.now().timestamp()) - message.latency# delay ou latencia que se chama?
                    self.tree[client][address[0]] = MeasureEntry(delay, 0) # FAZER O LOSS

            self.tree_lock.release()



    def tracking_service(self):
        wait = 20
        while True:
            for server in self.servers:
                self.control_socket.sendto(ControlPacket(ControlPacket.STATUS).serialize(), (server, 7777))

                self.logger.info(f"Tracking Service: Monitorization message sent to {server}")
                    
            time.sleep(wait) 



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
        RP(args.bootstrapper, is_bootstrapper=True, file=args.file, debug_mode=debug_mode)
    elif args.bootstrapper:
        RP(args.bootstrapper, debug_mode=debug_mode)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
