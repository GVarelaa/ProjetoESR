import argparse
import json
import threading
import logging
import time
import socket
from datetime import datetime
from node import Node
from packets.control_packet import ControlPacket
from utils.tree_entry import TreeEntry
from utils.status_entry import StatusEntry

class RP(Node):
    def __init__(self, bootstrapper, is_bootstrapper=False, file=None):        
        self.servers = list()

        self.servers_info_lock = threading.Lock()
        self.servers_info = dict()

        super().__init__(bootstrapper, is_bootstrapper=is_bootstrapper, file=file)

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
                    self.servers = msg.servers
                    
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

                if self.insert_tree(message, address): # Enviar para trás (source_ip=cliente)
                    message.response = 1
                    self.control_socket.sendto(message.serialize(), (address[0], 7777))
                    self.logger.info(f"Streaming Service: Subscription confirmation sent to {address[0]}")

                # MUDAR ISTO!!!!!!!!!!!!! SE ESTIVER A RECEBER A STREAM SO VAI REDIRECIONAR

                """
                # Proteger com condição
                best_server = None

                self.servers_info_lock.acquire()

                for server, status in self.servers_info.items():
                    if content in status.contents:
                        if best_server is not None:
                            if best_server[1] > status.metric:
                                best_server = (status.server, status.metric)
                        else:
                            best_server = (status.server, status.metric)
                
                self.servers_info_lock.release()

                message = ControlPacket(ControlPacket.PLAY, contents=[content])
                self.control_socket.sendto(message.serialize(), best_server[0]) # Proteger para casos em que ainda nao tem best server

                self.logger.info(f"Control Service: Stream request sent to server {best_server[0]}")
                self.logger.debug(f"Message sent: {message}")
                """
        
            elif message.response == 1:
                try:
                    while True:
                        data, address = self.data_socket.recvfrom(20480)
                    
                        for ip in ips:
                            self.data_socket.sendto(data, (ip, 7778))
                            self.logger.debug(f"Streaming Service: RTP Packet sent to {ip}")
                
                finally:
                    self.data_socket.close()
        
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

            self.servers_info_lock.acquire()

            self.servers_info[address[0]] = StatusEntry(address, latency, message.contents, True) 

            self.logger.info(f"Control Service: Status from {address} was updated")

            self.servers_info_lock.release()


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
    args = parser.parse_args()

    if args.file:
        RP(args.bootstrapper, is_bootstrapper=True, file=args.file)
    elif args.bootstrapper:
        RP(args.bootstrapper)
    else:
        print("Error: Wrong arguments")
        exit()


if __name__ == "__main__":
    main()
