import socket
import sys
from message import Message

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg = "teste"

    s.sendto(Message(0, [], msg).serialize(), ("10.0.1.1", 7777))

    msg_received, addr = s.recvfrom(1024)
    print(f"recebi a resposta: {Message.deserialize(msg_received)}")

    s.close()

if __name__ == "__main__":
    main()