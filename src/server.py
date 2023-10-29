import socket
import sys
import threading

def message_handler(s, msg, addr):
    print(f"recebi a mensagem: {msg.decode('utf-8')}")
    s.sendto("correu bem".encode("utf-8"), addr)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", 3000))

    try:
        while True:
            msg, addr = s.recvfrom(1024)
            
            #processamento da mensagem
            threading.Thread(target=message_handler, args=(s, msg, addr)).start()
    
    finally:
        s.close()

if __name__ == "__main__":
    main()
