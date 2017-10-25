# ServerAuth
Сервер на Python на который можно зайти. Пустота и сообщения.

# Вопросы

Как отправить пакет?

self.send_packet(IDпаекета, Дата пакета) ->

self.send_packet(0x18, Buffer.pack_string('BungeeCord') + u'Hello')  #http://wiki.vg/Protocol#Plugin_Message

Как отправить сообщение?

self.send_chat('Hello world!')

Как отправить Title? 

self.send_title('Line 1', 'Line 2')

Как создать задачу, которая будет выполнятся каждую секунду?

self.taks.add_loop(Секундны, self.метод)

Как создать задачу, которая выполнится через несколько секунд?

self.tasks.add_delay(Секунды, self.метод)

# Остались вопросы? 

Пишите их во вкладку Issues,помогу почти всем :)

# Wikis

# AuthProtocol
self.joined                       Boolean example:   print(str(self.joined))

self.need_to_send_keep_alive      Boolean example:   print(str(self.need_to_send_keep_alive))

self.client_addr                  String  example:   print(self.client_addr)

self.tasks                        Method  example:   none

self.timeout                      Int     example:   print(str(self.timeout))

self.protocol_version             Int     example:   print(str(self.protocol_version))

self.protocol_mode                Int     example:   print(str(self.protocol_mode))

self.username                     String  example:   print(self.username)

self.send_chat                    Method  example:   self.send_chat('Hello world')

self.send_title                   Method  example:   self.send_title('Line 1', 'Line 2')

self.send_packet                  Method  example:   self.send_packet(0x10, Buffer.pack('dddff', 0, 0, 0, 0, 0)) # http://wiki.vg/Protocol#Vehicle_Move

self.kick                         Method  example:   self.kick('You kicked')


# AuthServer
self.factory.s_port               Int     example:   print(str(self.s_port)) 

self.factory.s_host               String  example:   print(self.s_host)

self.factory.debug                Boolean example:   print(str(self.debug))

self.factory.motd                 String  example:   print(self.motd)

self.factory.status               Json    example:   print(str(self.status))



# Tasks
Tasks.tasks.add_loop               Method example:   self.tasks.add_loop(1, self.method)

Tasks.tasks.add_delay              Method example:   self.tasks.add_delay(1, self.method)

Tasks.tasks.stop_all               Method example:   self.tasks.stop_all()



# Buffer
Buffer.pack_varint                 Method example:   Buffer.pack_varint(0)

Buffer.pack_array                  Method example:   Buffer.pack_array

Buffer.pack_string                 Method example:   Buffer.pack_string

Buffer.pack_chat                   Method example:   Buffer.pack_chat

Buffer.pack_json                   Method example:   Buffer.pack_json

Buffer.pack                        Method example:   Buffer.pack

Buffer.unpack_varint               Method example:   Buffer.unpack_varint

Buffer.unpack_array                Method example:   Buffer.unpack_array

Buffer.unpack_string               Method example:   Buffer.unpack_string

Buffer.unpack                      Method example:   Buffer.unpack

Buffer.unpack_raw                  Method example:   Buffer.unpack_raw

