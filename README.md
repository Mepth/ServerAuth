![Logo](https://i.imgur.com/c49sAHm.png)
# ServerAuth
Сервер на Python на который можно зайти. Пустота и сообщения.

# Установка
```
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev python3-pip python3
pip3 install twisted cryptography pyOpenSSL service_identity
python main.py 25565
```
# Вопросы

Как отправить пакет?
```
self.send_packet(IDпаекета, Дата пакета) ->
```
```
self.send_packet('plugin_message', Buffer.pack_string('BungeeCord') + u'Hello')  #http://wiki.vg/Protocol#Plugin_Message
```
Как отправить сообщение?
```
self.send_chat('Hello world!')
```
Как отправить Title? 
```
self.send_title('Line 1', 'Line 2', 15, 100, 15)
```
Как создать задачу, которая будет выполнятся каждую секунду?
```
self.taks.add_loop(Секундны, self.метод)
```
Как создать задачу, которая выполнится через несколько секунд?
```
self.tasks.add_delay(Секунды, self.метод)
```
# Остались вопросы? 

Пишите их во вкладку Issues,помогу почти всем :)

# Типы для struct

 - Boolean: ?
 - Byte: b
 - Unsigned_byte: B
 - Short: h
 - Unsigned_short: H
 - Int: i
 - Long: q
 - Unsigned_long: Q
 - Float: f
 - Double: d
