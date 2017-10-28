#!/usr/bin/python
# -*- coding: utf-8 -*-
from twisted.internet import protocol, reactor
from twisted.internet.task import LoopingCall
import struct, json, zlib, sys, packets
class BufferUnderrun(Exception): pass
class Tasks(object):
    def __init__(self):
        self._tasks = []
    def add_loop(self, time, callback, *args):
        task = LoopingCall(callback, *args)
        task.start(time, now=False)
        self._tasks.append(task)
        return task
    def add_delay(self, time, callback, *args):
        task = reactor.callLater(time, callback, *args)
        def stop():
            if task.active(): task.cancel()
        def restart():
            if task.active(): task.reset(time)
        task.restart = restart
        task.stop = stop
        self._tasks.append(task)
        return task
    def stop_all(self):
        while len(self._tasks) > 0:
            task = self._tasks.pop(0)
            task.stop()
class ProtocolError(Exception):
    @classmethod
    def mode_mismatch(cls, ident, mode): return cls("Unexpected packet; ID: {0}; Mode: {1}".format(ident, mode))
    @classmethod
    def step_mismatch(cls, ident, step): return cls("Unexpected packet; ID: {0}; Step: {1}".format(ident, step))
class Buffer(object):
    def __init__(self): self.buff1, self.buff2 = "", ""
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
        self.x, self.y, self.z, self.o, self.expBar, self.bar, self.pps, self.guards, self.prog, self.hic, self.nhlc, self.gu = 1, 400, 0, True, 2, 0.0, 0, 0, False, 0, 0, 0
        self.joined = False
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
            if self.protocol_mode == 3:
                key = (self.protocol_version, self.get_mode(self.protocol_mode), "upstream", ident)
                try: name = packets.packet_names[key]
                except KeyError: raise ProtocolError("No name known for packet: %s" % (key,))
                if name == 'player_position': self.x, self.y, self.z, self.o = buff.unpack('ddd?')
                if name == 'held_item_change': self.nhlc = buff.unpack('h'); self.gu += 1
            self.pps += 1
            if self.protocol_mode == 0:
                if ident == 0:
                    self.protocol_version = buff.unpack_varint()
                    self.server_addr = buff.unpack_string()
                    self.server_port = buff.unpack("H")
                    self.protocol_mode = buff.unpack_varint()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 1:
                if ident == 0: self.send_packet("status_response", Buffer.pack_string(json.dumps(self.factory.get_status(self.protocol_version))))
                elif ident == 1:
                    time = buff.unpack("Q")
                    self.send_packet('status_pong', Buffer.pack("Q", time))
                    sys.stdout.write(self.client_addr + ' pinged\n')
                    self.close()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 2:
                self.username = buff.unpack_string()
                if not self.joined:
                    self.joined = True
                    self.send_packet('login_success', buff.pack_string('19e34a23-53d5-4bc2-a649-c9575ef08bb6') + buff.pack_string(self.username))
                    self.protocol_mode = 3
                    sys.stdout.write('%s joined on server with parms: %s|[%s]%s\n' % (self.username, self.protocol_version, self.client_addr, self.protocol_mode))
                    if self.protocol_version == 47:
                        self.send_packet('join_game', buff.pack('iBbBB', 0, 0, 0, 0, 0) + buff.pack_string('flat') + buff.pack('?', False))
                        self.send_packet('player_position_and_look', Buffer.pack('dddffb', float(0), float(400), float(0), float(-90), float(0), 0b00000))
                    elif self.protocol_version == 107:
                        self.send_packet('join_game', buff.pack('iBbBB', 0, 0, 0, 0, 0) + buff.pack_string('flat') + buff.pack('?', False))
                        self.send_packet('player_position_and_look', self.buff.pack('dddffb', float(0), float(400), float(0), float(-90), float(0), True) + self.buff.pack_varint(0))
                    else:
                        self.send_packet('join_game', self.buff.pack('iBiBB', 0, 0, 0, 0, 0) + self.buff.pack_string('flat') + self.buff.pack('?', False))
                        self.send_packet('player_position_and_look', self.buff.pack('dddff?', float(0), float(400), float(0), float(-90), float(0), True) + self.buff.pack_varint(0))
                    self.send_chunk()
                    self.send_chat('Ожидайте завершения проверки')
                    self.send_title('Wait', 'вы проверяйтесь')
                    self.tasks.add_loop(0.05, self.guard)
                    self.tasks.add_delay(15, self.time_kick)
            else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
        except: pass
    def guard(self):
        self.send_packet('update_health', Buffer.pack('f', self.expBar) + Buffer.pack_varint(self.expBar) + Buffer.pack('f', 0.0))
        self.send_packet('set_experience', Buffer.pack('f', self.bar) + Buffer.pack_varint(0) + Buffer.pack_varint(0))
        self.send_packet('held_item_change', Buffer.pack('b', self.hic))
        self.bar += 0.01695
        self.expBar += 1
        self.hic += 1
        if self.hic == 9: self.hic = 0
        if self.bar >= 1: self.bar = 0.1
        if self.expBar == 21: self.expBar = 1
        if self.pps >= 50 and self.y <= 390 and not self.prog and self.gu >= 40:
            self.prog = True
            self.send_chat('Success')
            sys.stdout.write('%s passed the test and was sent to the server: %s|[%s]%s\n' % (self.username, self.protocol_version, self.client_addr, self.protocol_mode))
    def send_packet(self, name, data):
        key = ( self.protocol_version, self.get_mode(self.protocol_mode), "downstream", name)
        try: ident = packets.packet_idents[key]
        except KeyError: raise ProtocolError("No ID known for packet: %s" % (key,))
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
        self.factory.online = self.factory.online - 1
        sys.stdout.write('leaved from server with parms: %s|[%s]%s\n' % (self.protocol_version, self.client_addr, self.protocol_mode))
    def kick(self, message):
        if self.get_mode(self.protocol_mode) == 'login': self.send_packet('login_disconnect', Buffer.pack_string(json.dumps({"text": message.replace('&', u'\u00A7')})))
        else: self.send_packet('disconnect', Buffer.pack_string(json.dumps({"text": message.replace('&', u'\u00A7')})))
        self.close()
    def time_kick(self):
        self.kick('CheckTimeOut')
    def send_title(self, message, sub):
        self.send_packet('title', Buffer.pack_varint(0) + Buffer.pack_chat(message))
        self.send_packet('title', Buffer.pack_varint(1) + Buffer.pack_chat(sub))
    def send_chunk(self):
        if self.protocol_version == 47: self.send_packet('chunk_data', Buffer.pack('ii?H', 0, 0, True, 0) + Buffer.pack_varint(0))
        elif self.protocol_version == 109 or self.protocol_version == 108 or self.protocol_version == 107: self.send_packet('chunk_data', Buffer.pack('ii?', 0, 0, True) + Buffer.pack_varint(0) + Buffer.pack_varint(0))
        else: self.send_packet('chunk_data', Buffer.pack('ii?H', 0, 0, True, 0) + Buffer.pack_varint(0))
    def send_chat(self, msg):
        self.send_packet('chat_message', Buffer.pack_chat(msg) + Buffer.pack('b', 0))
    def get_mode(self, mode):
        mm = ''
        if mode == 0: mm = 'init'
        if mode == 1: mm = 'status'
        if mode == 2: mm = 'login'
        if mode == 3: mm = 'play'
        return mm
class AuthServer(protocol.Factory):
    def __init__(self):
        self.s_port = 48000
        self.s_host = '0.0.0.0'
        self.online = 0
        self.debug = False
        self.motd = "&dAuthServer by vk.com/ru.yooxa\n&71.8-1.12.2"
        self.player_timeout = 30
        self.status = {"description": self.motd.replace('&', u'\u00A7'),"players": {"max": 0, "online": self.online},"version": {"name": "", "protocol": 0}}
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
