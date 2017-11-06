#!/usr/bin/python
# -*- coding: utf-8 -*-
from twisted.internet import protocol, reactor
from twisted.internet.task import LoopingCall
from os.path import abspath
from plugin_core import PluginSystem
import struct, json, zlib, sys, packets, random
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
    def mode_mismatch(cls, ident, mode): return cls('Unexpected packet; ID: {0}; Mode: {1}'.format(ident, mode))
    @classmethod
    def step_mismatch(cls, ident, step): return cls('Unexpected packet; ID: {0}; Step: {1}'.format(ident, step))
class Buffer(object):
    def __init__(self):
        self.buff1 = b''
        self.buff2 = b''
    def length(self): return len(self.buff1)
    def add(self, data): self.buff1 += data
    def save(self): self.buff2 = self.buff1
    def restore(self): self.buff1 = self.buff2
    def unpack_raw(self, l):
        if len(self.buff1) < l: raise BufferUnderrun()
        d, self.buff1 = self.buff1[:l], self.buff1[l:]
        return d
    def unpack(self, ty):
        s = struct.unpack('>'+ty, self.unpack_raw(struct.calcsize(ty)))
        return s[0] if len(ty) == 1 else s
    def unpack_string(self): return self.unpack_raw(self.unpack_varint()).decode('utf-8')
    def unpack_array(self): return self.unpack_raw(self.unpack('h'))
    def unpack_varint(self):
        d = 0
        for i in range(5):
            b = self.unpack('B')
            d |= (b & 0x7F) << 7*i
            if not b & 0x80: break
        return d
    def unpack_json(self):
        obj = json.loads(self.unpack_string())
        return obj
    def unpack_chat(self): return self.unpack_json()
    @classmethod
    def pack_uuid(cls, uuid): return uuid.to_bytes()
    @classmethod
    def pack_json(cls, obj): return cls.pack_string(json.dumps(obj))
    @classmethod
    def pack_chat(cls, text): return cls.pack_json({'text': text})
    @classmethod
    def pack(cls, ty, *data): return struct.pack('>'+ty, *data)
    @classmethod
    def pack_slot(cls, id=-1, count=1, damage=0, tag=None): return cls.pack('hbh', id, count, damage) + cls.pack_nbt(tag)
    @classmethod
    def pack_nbt(cls, tag=None):
        if tag is None: return b'\x00'
        return tag.to_bytes()
    @classmethod
    def pack_string(cls, data):
        data = data.encode('utf-8')
        return cls.pack_varint(len(data)) + data
    @classmethod
    def pack_array(cls, data): return cls.pack('h', len(data)) + data
    @classmethod
    def pack_varint(cls, d):
        o = b''
        while True:
            b = d & 0x7F
            d >>= 7
            o += struct.pack('B', b | (0x80 if d > 0 else 0))
            if d == 0: break
        return o
class AuthProtocol(protocol.Protocol):
    protocol_mode = 0
    protocol_version = 0
    login_step = 0
    def __init__(self, factory, addr):
        self.x, self.y, self.z, self.on_ground, self.slot = 1, 400, 0, True, 0
        self.joined = False
        self.factory = factory
        self.client_addr = addr.host
        self.buff = Buffer()
        self.tasks = Tasks()
        self.cipher = lambda d: d
        self.timeout = reactor.callLater(self.factory.player_timeout, self.kick, 'long to log in!')
    def dataReceived(self, data):
        self.buff.add(data)
        while True:
            try:
                packet_length = self.buff.unpack_varint()
                packet_body = self.buff.unpack_raw(packet_length)
                try: self.packet_received(packet_body)
                except ProtocolError as e:
                    print('Protocol Error: ', e)
                    self.kick('Protocol Error!\n\n%s' % (e))
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
                key = (self.protocol_version, self.get_mode(self.protocol_mode), 'upstream', ident)
                try: name = packets.packet_names[key]
                except KeyError: raise ProtocolError('No name known for packet: %s' % (key,))
                self.plugin_event('packet_recived', ident, name)
                if self.factory.debug: print(str(name))
                if name == 'player_position':
                    self.x, self.y, self.z, self.o = buff.unpack('ddd?')
                    self.plugin_event('player_move', self.x, self.y, self.z, self.on_ground)
                if name == 'held_item_change': self.s = buff.unpack('h')
                if name == 'chat_message':
                    self.chat_message = buff.unpack_string()
                    self.plugin_event('chat_message', self.chat_message)
                    if self.chat_message[0] == '/': self.handle_command(self.chat_message[1:])
                    else: self.send_chat_all(self.chat_message)
            if self.protocol_mode == 0:
                if ident == 0:
                    self.protocol_version = buff.unpack_varint()
                    self.server_addr = buff.unpack_string()
                    self.server_port = buff.unpack('H')
                    self.protocol_mode = buff.unpack_varint()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 1:
                if ident == 0: self.send_packet('status_response', self.buff.pack_string(json.dumps(self.factory.get_status(self.protocol_version))))
                elif ident == 1:
                    time = buff.unpack('Q')
                    self.send_packet('status_pong', self.buff.pack('Q', time))
                    sys.stdout.write(self.client_addr + ' pinged\n')
                    self.close()
                else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
            elif self.protocol_mode == 2:
                self.username = buff.unpack_string()
                if not self.joined:
                    self.joined = True
                    self.send_packet('login_success', buff.pack_string('19e34a23-53d5-4bc2-a649-c9575ef08bb6') + buff.pack_string(self.username))
                    self.protocol_mode = 3
                    self.factory.players.add(self)
                    for player in self.factory.players:
                        player.send_packet('chat_message', self.buff.pack_chat('§e%s joined on server!' % (self.username)) + self.buff.pack('b', 0))
                    sys.stdout.write('%s joined on server with parms: %s|[%s]%s\n' % (self.username, self.protocol_version, self.client_addr, self.protocol_mode))
                    if self.protocol_version == 47:
                        self.send_packet('join_game', buff.pack('iBbBB', 0, 0, 0, 0, 0) + buff.pack_string('flat') + buff.pack('?', False))
                        self.send_packet('player_position_and_look', self.buff.pack('dddffb', float(0), float(400), float(0), float(-90), float(0), 0b00000))
                    elif self.protocol_version == 107:
                        self.send_packet('join_game', buff.pack('iBbBB', 0, 0, 0, 0, 0) + buff.pack_string('flat') + buff.pack('?', False))
                        self.send_packet('player_position_and_look', self.buff.pack('dddffb', float(0), float(400), float(0), float(-90), float(0), True) + self.buff.pack_varint(0))
                    else:
                        self.send_packet('join_game', self.buff.pack('iBiBB', 0, 0, 0, 0, 0) + self.buff.pack_string('flat') + self.buff.pack('?', False))
                        self.send_packet('player_position_and_look', self.buff.pack('dddff?', float(0), float(400), float(0), float(-90), float(0), True) + self.buff.pack_varint(0))
                    self.send_chunk()
                    self.plugin_event('player_join')
                    self.tasks.add_loop(5, self.send_keep_alive)
            else: raise ProtocolError.mode_mismatch(ident, self.protocol_mode)
        except: pass
    def send_packet(self, name, data):
        key = (self.protocol_version, self.get_mode(self.protocol_mode), 'downstream', name)
        try: ident = packets.packet_idents[key]
        except KeyError: raise ProtocolError('No ID known for packet: %s' % (key,))
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
        if self.get_mode(self.protocol_mode) in ('login', 'play'):
            self.factory.players.discard(self)
            self.plugin_event('player_leave')
            for player in self.factory.players:
                player.send_packet('chat_message', self.buff.pack_chat('§e%s leaved from server!' % (self.username)) + self.buff.pack('b', 0))
        sys.stdout.write('leaved from server with parms: %s|[%s]%s\n' % (self.protocol_version, self.client_addr, self.protocol_mode))
    def kick(self, message):
        if self.get_mode(self.protocol_mode) == 'login': self.send_packet('login_disconnect', self.buff.pack_chat(message.replace('&', u'\u00A7')))
        else: self.send_packet('disconnect', self.buff.pack_chat(message.replace('&', u'\u00A7')))
        self.close()
    def send_title(self, message, sub, fadein, stay, fadeout):
        self.send_packet('title', self.buff.pack_varint(0) + self.buff.pack_chat(message))
        self.send_packet('title', self.buff.pack_varint(1) + self.buff.pack_chat(sub))
        if self.protocol_version <= 210: self.send_packet('title', self.buff.pack_varint(2) + self.buff.pack('iii', fadein, stay, fadeout))
        else: self.send_packet('title', self.buff.pack_varint(3) + self.buff.pack('iii', fadein, stay, fadeout))
    def send_chunk(self):
        if self.protocol_version == 47: self.send_packet('chunk_data', self.buff.pack('ii?H', 0, 0, True, 0) + self.buff.pack_varint(0))
        elif self.protocol_version == 109 or self.protocol_version == 108 or self.protocol_version == 107: self.send_packet('chunk_data', self.buff.pack('ii?', 0, 0, True) + self.buff.pack_varint(0) + self.buff.pack_varint(0))
        else: self.send_packet('chunk_data', self.buff.pack('ii?H', 0, 0, True, 0) + self.buff.pack_varint(0))
    def send_spawn_player(self, entity_id, player_uuid, x, y, z, yaw, pitch):
        self.send_packet("spawn_player", self.buff.pack_varint(entity_id) + self.buff.pack_uuid(player_uuid) + self.buff_type.pack('dddbbBdb', x, y, z, yaw, pitch, 0, 7, 20))
    def send_held_item_change(self, slot):
        self.send_packet('held_item_change', self.buff.pack('b', slot))
    def send_update_health(self, heal, food):
        self.send_packet('update_health', self.buff.pack('f', heal) + self.buff.pack_varint(food) + self.buff.pack('f', 0.0))
    def send_set_experience(self, exp, lvl):
        self.send_packet('set_experience', self.buff.pack('f', exp) + self.buff.pack_varint(lvl) + self.buff.pack_varint(0))
    def send_chat(self, msg):
        self.send_packet('chat_message', self.buff.pack_chat(msg) + self.buff.pack('b', 0))
    def send_chat_all(self, msg):
        sys.stdout.write('<%s>: %s\n' % (self.username, msg))
        for player in self.factory.players:
            player.send_packet('chat_message', self.buff.pack_chat('<' + self.username + '> ' + msg) + self.buff.pack('b', 0))
    def send_player_list_header_footer(self, up, down):
        self.send_packet('player_list_header_footer', self.buff.pack_chat(up) + self.buff.pack_chat(down))
    def send_set_slot(self, id, count, slot, window=0):
        self.send_packet('set_slot', self.buff.pack('bh', window, slot) + self.buff.pack_slot(id, count, 0, None))
    def send_keep_alive(self):
        if self.protocol_version <= 338: payload = self.buff.pack_varint(0)
        else: payload = self.buff.pack('Q', 0)
        self.send_packet('keep_alive', payload)
    def set_position(self, x, y, z):
        self.send_packet('player_position_and_look', self.buff.pack('dddff?', float(x), float(y), float(z), float(-90), float(0), True))
    def kick_all(self, msg):
        for player in self.factory.players:
            player.kick(msg)
    def handle_command(self, command_string):
        print('Player ' + self.username + ' issued server command: ' + command_string + '')
        command_list = command_string.split(' ')
        command, arguments = command_list[0], command_string.split(' ')[1:]
        self.plugin_event('player_command', command, arguments)
    def get_mode(self, mode):
        mm = ''
        if mode == 0: mm = 'init'
        if mode == 1: mm = 'status'
        if mode == 2: mm = 'login'
        if mode == 3: mm = 'play'
        return mm
    def plugin_event(self, event_name, *args, **kwargs):
        self.factory.plugin_system.call_event(event_name, self, *args, **kwargs)
class AuthServer(protocol.Factory):
    def __init__(self):
        if not len(sys.argv) == 2:
            print('Port invalid')
            sys.exit()
        self.s_port = int(sys.argv[1])
        self.s_host = '0.0.0.0'
        self.debug = False
        self.players = set()
        self.plugin_system = PluginSystem(folder=abspath('plugins'))
        self.plugin_system.register_events()
        self.motd = '&dAuthServer by vk.com/ru.yooxa\n&71.8-1.12.2'
        self.player_timeout = 30
        self.status = {'description': self.motd.replace('&', u'\u00A7'),'players': {'max': 0, 'online': len(self.players)},'version': {'name': '', 'protocol': 0}}
    def run(self):
        reactor.listenTCP(self.s_port, self, interface=self.s_host)
        print('server binded on ' + self.s_host + ':' + str(self.s_port))
        reactor.run()
    def buildProtocol(self, addr): return AuthProtocol(self, addr)
    def get_status(self, protocol_version):
        d = dict(self.status)
        d['version']['protocol'] = protocol_version
        return d
if __name__ == '__main__':
    server = AuthServer()
    server.run()
