from node import Node

class RP(Node):
    def __init__(bootstrapper):
        super.__init__(bootstrapper=bootstrapper)

    
    def subscription_worker(self, addr, msg):
        # Enviar ack para trás
        ack_msg = copy.deepcopy(msg)
        ack_msg.flag = 1

        self.control_socket.sendto(ack_msg.serialize(), addr)
        self.logger.info(f"Control Service: Acknowledgment message sent to {addr[0]}")
        self.logger.debug(f"Ack message sent: {msg}")

        if msg.data is None:
            msg.data = list()
        msg.data.append(addr[0])

        self.database.insert(msg.data[0], addr[0], msg.timestamp)


