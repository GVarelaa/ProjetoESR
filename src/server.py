import argparse
import socket
import threading
import logging
import time
from datetime import datetime
from random import randint
from utils.videostream import VideoStream
from packets.rtp_packet import RtpPacket
from packets.control_packet import ControlPacket

class Server:
    def __init__(self, filenames, debug_mode=False):
        self.videostreams = dict()
        for file in filenames:
            self.videostreams[file] = VideoStream("../videos/"+file)
            
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket.bind(('', 7777))
        self.event = threading.Event()
        #self.worker = threading.Thread(target=self.send_rtp).start()

        if debug_mode:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.DEBUG)
        else:
            logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
        self.logger = logging.getLogger()
        self.logger.info(f"Streaming service listening on port {self.control_socket.getsockname()[1]}")

        self.control_service()


    def control_worker(self, addr, msg):
        """Process RTSP request sent from the client."""
        # Get the media file name
        #filename = line1[1]
        
        # Get the RTSP sequence number 
        #seq = request[1].split(' ')
        
        if msg.type == ControlPacket.PLAY and msg.response == 0:
            filename = msg.contents[0]

            if filename in self.videostreams:
                send_stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
                # Create a new thread and start sending RTP packets
                #self.event = threading.Event()
                threading.Thread(target=self.send_rtp, args=(addr, send_stream_socket, filename)).start()
            else:
                msg.error = 1
                self.control_socket.sendto(msg.serialize(), addr) # O ficheiro não está nas streams
        
        elif msg.type == ControlPacket.STATUS and msg.response == 0:
            actual_timestamp = float(datetime.now().timestamp())
            
            msg = ControlPacket(ControlPacket.STATUS, response=1, latency=actual_timestamp, contents=list(self.videostreams.keys()))
            self.control_socket.sendto(msg.serialize(), addr)

            self.logger.info(f"Control Service: Metrics sent to {addr[0]}")
            self.logger.debug(f"Message sent: {msg}")


    def control_service(self):
        try:
            while True:
                msg, addr = self.control_socket.recvfrom(1024)
                msg = ControlPacket.deserialize(msg)

                self.logger.info(f"Control Service: Message received from {addr[0]}")
                self.logger.debug(f"Message received: {msg}")
                
                threading.Thread(target=self.control_worker, args=(addr, msg,)).start()

        finally:
            self.control_socket.close()


    def send_rtp(self, addr, send_stream_socket, filename):
        """Send RTP packets over UDP."""
        while True:
            self.event.wait(0.05)
            
            # Stop sending if request is PAUSE or TEARDOWN
            #if self.event.isSet():
            #    break
                
            data = self.videostreams[filename].get_next_frame()
            
            if data:
                frame_nr = self.videostreams[filename].get_frame_nr()
                try:
                    packet =  self.make_rtp(data, frame_nr)
                    send_stream_socket.sendto(packet, (addr[0], 7778))

                    self.logger.debug(f"Streaming Service: RTP Packet {frame_nr} sent to {addr[0]}")
                except:
                    self.logger.debug(f"Streaming Service: An error occurred sending RTP Packet {frame_nr} to {addr[0]}")


    def make_rtp(self, payload, frame_nr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26 # MJPEG type
        seqnum = frame_nr
        ssrc = 0
        
        rtpPacket = RtpPacket()
        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
        
        return rtpPacket.get_packet()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-videostreams", help="filenames", type=lambda arg: arg.split(" "))
    parser.add_argument("-d", action="store_true", help="activate debug mode")
    args = parser.parse_args()

    debug_mode = False

    if args.d:
        debug_mode = True

    server = Server(args.videostreams, debug_mode=debug_mode)


if __name__ == "__main__":
    main()