import time, zlib

class CCSDSProtocol:
    def __init__(self):
        self.seq = 0

    def create_packet(self, data):
        self.seq += 1
        packet = {
            'header': {'version':1,'type':'TELEMETRY','seq':self.seq,'timestamp':int(time.time())},
            'body': data,
            'crc': 0
        }
        packet['crc'] = zlib.crc32(str(packet).encode())
        return packet
