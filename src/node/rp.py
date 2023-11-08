import threading
import copy
import time
from .node import Node
from message import Message

class RP(Node):
    def __init__(self, bootstrapper):
        super().__init__(bootstrapper=bootstrapper)

        self.tracking_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tracking_socket.bind(("", 7780))

    
    def subscription_worker(self, addr, msg):
        # Enviar ack para trás
        ack_msg = copy.deepcopy(msg)
        ack_msg.flag = 1

        self.control_socket.sendto(ack_msg.serialize(), addr)
        self.logger.info(f"Control Service: Acknowledgment message sent to {addr[0]}")
        self.logger.debug(f"Ack message sent: {msg}")
        
        msg.hops.append(addr[0])

        self.database.insert(msg.hops[0], addr[0], msg.timestamp)

    
    def tracking_service(self):
        wait = 20
        while True:
            for neighbour in self.database.neighbours:
                message = Message(4)
                try:
                    response = self.send_udp(message, 3, 2, "Tracking Service", neighbour, self.tracking_socket)
                    
                    if response.type == 4:
                        self.database.insert_servers(response.source_ip, latency, response.contents)

                        self.logger.info("Control Service: Neighbours received")
                        self.logger.debug(f"Neighbours: {self.database.neighbours}")

                except ACKFailed:
                    self.logger.info("Tracking Service: Could not receive an acknowledgment from tracking request after 3 retries")

            time.sleep(wait)

