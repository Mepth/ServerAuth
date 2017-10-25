#!/usr/bin/python
# -*- coding: utf-8 -*-
from twisted.internet import protocol, reactor
from twisted.internet.task import LoopingCall
import struct, json, zlib, sys
class BufferUnderrun(Exception): pass
class Tasks(object):
    def __init__(self):
        self._tasks = []
    def add_loop(self, time, callback, *args): #выполнять в цикле
        task = LoopingCall(callback, *args)
        task.start(time, now=False)
        self._tasks.append(task)
        return task
    def add_delay(self, time, callback, *args): #выполнить через N секнуд
        task = reactor.callLater(time, callback, *args)
        self._tasks.append(task)
        return task
    def stop_all(self): #Остановить все задачи игрока
        while len(self._tasks) > 0:
            task = self._tasks.pop(0)
            task.stop()
class ProtocolError(Exception):
    @classmethod
    def mode_mismatch(cls, ident, mode): return cls("Unexpected packet; ID: {0}; Mode: {1}".format(ident, mode))
    @classmethod
    def step_mismatch(cls, ident, step): return cls("Unexpected packet; ID: {0}; Step: {1}".format(ident, step))
class Buffer(object):
    def __init__(self):
        self.buff1 = ""
        self.buff2 = ""
    def length(self): return len(self.buff1)
    def add(self, d): self.buff1 += d
    def save(self): self.buff2 = self.buff1
    def restore(self): self.buff1 = self.buff2
    def unpack_raw(self, l):
        if len(self.buff1) < l: raise BufferUnderrun()
        d, self.buff1 = self.buff1[:l], self.buff1[l:]
        return d
    def unpack(self, ty):
        s = struct.unpack(">"+ty, self.unpack_raw(struct.calcsize(ty)))
        return s[0] if len(ty) == 1 else s
    def unpack_string(self): return self.unpack_raw(self.unpack_varint()).decode("utf-8")
    def unpack_array(self): return self.unpack_raw(self.unpack("h"))
    def unpack_varint(self):
        d = 0
        for i in range(5):
            b = self.unpack("B")
            d |= (b & 0x7F) << 7*i
            if not b & 0x80: break
        return d
    @classmethod
    def pack_json(cls, obj): return cls.pack_string(json.dumps(obj))
    @classmethod
    def pack_chat(cls, text): return cls.pack_json({"text": text})
    @classmethod
    def pack(cls, ty, *data): return struct.pack(">"+ty, *data)
    @classmethod
    def pack_string(cls, data):
        data = data.encode("utf-8")
        return cls.pack_varint(len(data)) + data
    @classmethod
    def pack_array(cls, data): return cls.pack("h", len(data)) + data
    @classmethod
    def pack_varint(cls, d):
        o = ""
        while True:
            b = d & 0x7F
            d >>= 7
            o += cls.pack("B", b | (0x80 if d > 0 else 0))
            if d == 0: break
        return o
class AuthProtocol(protocol.Protocol):
    protocol_mode = 0
    protocol_version = 0
    login_step = 0
    def __init__(self, factory, addr):
        self.x, self.y, self.z, self.o = 0, 255, 0, True
        self.joined = False
        self.need_to_send_keep_alive = False
        self.factory = factory
        self.client_addr = addr.host
        self.buff = Buffer()
        self.tasks = Tasks()
        self.cipher = lambda d: d
        self.timeout = reactor.callLater(self.factory.player_timeout, self.kick, "long to log in!")
    def dataReceived(self, data):
        self.buff.add(data)
        while True:
            try:
                packet_length = self.buff.unpack_varint()
                packet_body = self.buff.unpack_raw(packet_length)
                try: self.packet_received(packet_body)
                except ProtocolError as e:
                    print "Protocol Error: ", e
                    self.kick("Protocol Error!\n\n%s" % (e))
                    break
                self.buff.save()
            except BufferUnderrun: break
    def packet_received(self, data):
        buff = Buffer()
        buff.add(data)
        try:
            ident = buff.unpack_varint()
            if self.factory.debug: print(str(ident))
            if self.protocol_version == 47:
                if ident == 4: self.x, self.y, self.z, self.o = buff.unpack('ddd?')
            elif self.protocol_version == 107 or self.protocol_version == 108 or self.protocol_version == 109 or self.protocol_version == 110 or self.protocol_version == 210 or self.protocol_version == 315 or self.protocol_version == 316:
                if ident == 0x0C: self.x, self.y, self.z, self.o = buff.unpack('ddd?')
            elif self.protocol_version == 335 or self.protocol_version == 338 or self.protocol_version == 340:
                if ident == 0x0E: self.x, self.y, self.z, self.o = buff.unpack('ddd?')
            if self.protocol_mode == 0:
                if ident == 0:
                    self.protocol_version = buff.unpack_varint()
                    self.server_addr = buff.unpack_string()
                    self.server_port = buff.unpack("H")
                    self.protocol_mode = buff.unpack_varint()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 1:
                if ident == 0: self.send_packet(0, Buffer.pack_string(json.dumps(self.factory.get_status(self.protocol_version))))
                elif ident == 1:
                    time = buff.unpack("Q")
                    self.send_packet(1, Buffer.pack("Q", time))
                    sys.stdout.write(self.client_addr + ' pinged\n')
                    self.close()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 2:
                self.username = buff.unpack_string()
                print(str(self.y))
                '''
                if self.need_to_send_keep_alive:
                    if self.protocol_version == 47: self.send_packet(0x0, self.buff.pack_varint(0))
                    elif self.protocol_version == 338 or self.protocol_version == 340: self.send_packet(0x1F, self.buff.pack('Q', 0))
                    else: self.send_packet(0x1F, self.buff.pack_varint(0))
                '''
                if not self.joined:
                    self.joined = True
                    self.send_packet(0x2, buff.pack_string('19e34a23-53d5-4bc2-a649-c9575ef08bb6') + buff.pack_string(self.username))
                    self.need_to_send_keep_alive = True
                    sys.stdout.write('%s joined on server with parms: %s|[%s]%s\n' % (self.username, self.protocol_version, self.client_addr, self.protocol_mode))
                    if self.protocol_version == 47:
                        self.send_packet(0x1, Buffer.pack('iBbBB', 0, 3, 0, 0, 0) + Buffer.pack_string('flat') + Buffer.pack('?', False))
                        self.send_packet(0x8, Buffer.pack('dddffb', float(0), float(255), float(0), float(-90), float(0), 0b00000))
                    elif self.protocol_version == 316 or self.protocol_version == 315 or self.protocol_version == 110 or \
                        self.protocol_version == 210 or self.protocol_version == 109 or self.protocol_version == 108 or \
                        self.protocol_version == 107 or self.protocol_version == 335:
                        self.send_packet(0x23, Buffer.pack('iBiBB', 0, 3, 0, 0, 0) + Buffer.pack_string('flat') + Buffer.pack('?', False))
                        self.send_packet(0x2E, Buffer.pack('dddff?', float(0), float(255), float(0), float(-90), float(0), True) + Buffer.pack_varint(0))
                    elif self.protocol_version == 338 or self.protocol_version == 340:
                        self.send_packet(0x23, Buffer.pack('iBiBB', 0, 3, 0, 0, 0) + Buffer.pack_string('flat') + Buffer.pack('?', False))
                        self.send_packet(0x2F, Buffer.pack('dddff?', float(0), float(255), float(0), float(-90), float(0), True) + Buffer.pack_varint(0))
                    else: self.kick('Unsupported version')
                    self.send_chat('You joined on authserver')
                    self.send_title('§cНу ты это там залогинся /login [пароль]', '§eИли зарегайся /reg [пароль] [пароль]')
            else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
        except: pass
    def send_packet(self, ident, data):
        data = Buffer.pack_varint(ident) + data
        data = Buffer.pack_varint(len(data)) + data
        if len(data) >= 256: data = Buffer.pack_varint(len(data)) + zlib.compress(data)
        else: data = Buffer.pack_varint(0) + data
        data = self.cipher(data)
        self.transport.write(data)
    def close(self):
        if self.timeout.active(): self.timeout.cancel()
        self.transport.loseConnection()
    def connectionLost(self, reason=None):
        self.tasks.stop_all()
        sys.stdout.write('leaved from server with parms: %s|[%s]%s\n' % (self.protocol_version, self.client_addr, self.protocol_mode))
    def kick(self, message):
        self.send_packet(0, Buffer.pack_string(json.dumps({"text": message.replace('&', u'\u00A7')})))
        self.close()
    def send_title(self, message, sub):
        if self.protocol_version <= 334:
            self.send_packet(0x45, Buffer.pack_varint(0) + Buffer.pack_chat(message))
            self.send_packet(0x45, Buffer.pack_varint(1) + Buffer.pack_chat(sub))
        elif self.protocol_version == 335:
            self.send_packet(0x47, Buffer.pack_varint(0) + Buffer.pack_chat(message))
            self.send_packet(0x47, Buffer.pack_varint(1) + Buffer.pack_chat(sub))
        elif self.protocol_version == 338 or self.protocol_version == 340:
            self.send_packet(0x48, Buffer.pack_varint(0) + Buffer.pack_chat(message))
            self.send_packet(0x48, Buffer.pack_varint(1) + Buffer.pack_chat(sub))
    def send_chat(self, msg):
        if self.protocol_version == 47:
            self.send_packet(2, Buffer.pack_chat(msg) + Buffer.pack('b', 0))
        elif self.protocol_version == 316 or self.protocol_version == 315 or self.protocol_version == 110 or \
                        self.protocol_version == 210 or self.protocol_version == 109 or self.protocol_version == 108 or \
                        self.protocol_version == 107 or self.protocol_version == 335 or self.protocol_version == 338 or self.protocol_version == 340:
            self.send_packet(0x0F, Buffer.pack_chat(msg) + Buffer.pack('b', 0))
class AuthServer(protocol.Factory):
    def __init__(self):
        self.s_port = 25565
        self.s_host = '0.0.0.0'
        self.debug = False
        self.motd = "&dAuthServer by vk.com/ru.yooxa\n&71.8-1.12.2"
        self.player_timeout = 30
        self.status = {"description": self.motd.replace('&', u'\u00A7'),"players": {"max": 0, "online": 0},"version": {"name": "", "protocol": 0}}
    def run(self):
        reactor.listenTCP(self.s_port, self, interface=self.s_host)
        print("server binded on " + self.s_host + ":" + str(self.s_port))
        reactor.run()
    def buildProtocol(self, addr): return AuthProtocol(self, addr)
    def get_status(self, protocol_version):
        d = dict(self.status)
        d["version"]["protocol"] = protocol_version
        return d
if __name__ == "__main__":
    server = AuthServer()
    server.run()
