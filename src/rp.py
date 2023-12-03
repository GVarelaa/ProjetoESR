import argparse
import threading
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
                        self.servers[server] = StatusEntry()
                    
                    self.logger.info("Setup: Neighbours and servers received")
                    self.logger.debug(f"Neighbours: {self.neighbours}")
                    self.logger.debug(f"Servers: {self.servers}")
                
                else:
                    self.logger.info("Setup: Unexpected response received")
                    exit() # É este o comportamento que queremos ?
                
            except socket.timeout:
                self.logger.info("Setup: Could not receive response to neighbours and servers request")
                exit()


    def control_worker(self, address, msg):
        # Se tem ciclos
        if address[0] in msg.hops:
            return
        
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
            if msg.response == 0:
                self.logger.info(f"Control Service: Subscription message received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                self.last_contacts_lock.acquire()
                self.last_contacts[msg.hops[0]] = float(datetime.now().timestamp())
                self.last_contacts_lock.release()

                self.insert_tree(msg, address) # Enviar para trás (source_ip=cliente)

                content = msg.contents[0]
                if content not in self.streams: # Se não está a streamar então vai contactar o melhor servidor com aquele conteudo pra lhe pedir a stream
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
                        if content in value.contents:
                            if best_server is not None:
                                if best_server[1] > value.metric:
                                    best_server = (server, value.metric)
                            else:
                                best_server = (server, value.metric)
                    self.servers_lock.release()

                    self.control_socket.sendto(ControlPacket(ControlPacket.PLAY, port=port, contents=[content]).serialize(), (best_server[0], 7777)) # Proteger para casos em que ainda nao tem best server

                    self.servers[best_server[0]].status = True # Verificar dps

                    self.logger.info(f"Control Service: Streaming request sent to server {best_server[0]}")
                    self.logger.debug(f"Message sent: {msg}")

                    # LANÇAMOS AQUI UMA THREAD PARA RECEBER A STREAM?
                    threading.Thread(target=self.listen_rtp, args=(port, content)).start()

        
        elif msg.type == ControlPacket.LEAVE:
            self.logger.info(f"Control Service: Leave message received from neighbour {address[0]}")
            self.logger.debug(f"Message received: {msg}")

            content = msg.contents[0]

            self.tree_lock.acquire()

            if content in self.tree:
                if address[0] in self.tree[content]:
                    self.tree[content].pop(address[0])
                    
                    if len(list(self.tree[content].keys())) == 0:
                        self.streams_lock.acquire()
                        self.streams.pop(content)
                        self.streams_lock.release()

            self.tree_lock.release()
            
            self.logger.debug(f"Control Service: Client {address[0]} was removed from tree")
        
        elif msg.type == ControlPacket.MEASURE:
            if msg.response == 0:
                self.logger.info(f"Control Service: Measure request received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                msg.response = 1
                self.control_socket.sendto(msg.serialize(), (address[0], 7777))
            
            elif msg.response == 1:
                # TER CUIDADO COM AS INTERFACES
                self.logger.info(f"Control Service: Measure response received from neighbour {address[0]}")
                self.logger.debug(f"Message received: {msg}")

                self.tree_lock.acquire()
                
                for content, clients in self.tree.items():
                    for client in clients:
                        if address[0] in self.tree[content][client]:
                            delay = float(datetime.now().timestamp()) - msg.latency# delay ou latencia que se chama?
                            self.tree[content][client][address[0]] = MeasureEntry(delay, 0) # FAZER O LOSS

                self.tree_lock.release()


    def tracking_service(self):
        tracking_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tracking_socket.bind(("", 5000))
        
        delay = 2
        tracking_socket.settimeout(delay)

        wait = 6
        while True:
            for server in self.servers:
                initial_timestamp = datetime.now()
                tracking_socket.sendto(ControlPacket(ControlPacket.STATUS).serialize(), (server, 7777))

                self.logger.info(f"Tracking Service: Monitorization messages sent to {server}")

                try:
                    data, address = tracking_socket.recvfrom(1024)
                    msg = ControlPacket.deserialize(data)

                    self.servers_lock.acquire()
                    self.servers[address[0]].update_metrics(True, delay, initial_timestamp=initial_timestamp, final_timestamp=datetime.now(), contents=msg.contents)
                    self.servers_lock.release()

                    self.logger.info(f"Tracking Service: Metrics updated for {server}")
                
                except socket.timeout:
                    self.servers_lock.acquire()
                    self.servers[server].update_metrics(False, delay)
                    self.servers_lock.release()

                    self.logger.info(f"Tracking Service: Timeout occurred for {server}")

            # Update do servidor se necessário
            self.streams_lock.acquire()
            for stream in self.streams:
                best_server = None
                streaming_server = None

                self.servers_lock.acquire()
                for server, value in self.servers.items():
                    if stream in value.contents:
                        if value.status:
                            streaming_server = server
                        if best_server is not None:
                            if best_server[1] > value.metric:
                                best_server = (server, value.metric)
                        else:
                            best_server = (server, value.metric)
                self.servers_lock.release()
                
                if best_server != streaming_server:
                    tracking_socket.sendto(ControlPacket(ControlPacket.LEAVE, contents=[stream]).serialize(), (streaming_server, 7777))
                    
                    tracking_socket.sendto(ControlPacket(ControlPacket.PLAY, port=self.ports[stream], frame_number=self.streams[stream], contents=[stream]).serialize(), (best_server[0], 7777))

                    self.servers[streaming_server].status = False
                    self.servers[best_server[0]].status = True
            
            self.streams_lock.release()

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
