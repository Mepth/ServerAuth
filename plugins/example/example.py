from plugin_core import Plugin
import time
plugin = Plugin(name="example", description="example plugin", version="")
@plugin.event('player_join')
def join(player):
    player.send_chat('Hello this message from plugin')
@plugin.event('player_command')
def command(player, command, args):
    if command == 'stop':
        player.kick_all('Server stopped')
        plugin.log(player.username + ' has stopped server')
        time.sleep( 1 )
        from twisted.internet import reactor
        reactor.removeAll()
        reactor.iterate()
        reactor.stop()
    if command == 'tp':
        if len(args) == 3:
            x, y, z = args[0], args[1], args[2]
            player.set_position(x, y, z)
            player.send_chat('Teleported to X:%s Y:%s Z:%s' % (str(x), str(y), str(z)))
        else:
            player.send_chat('Need 3 args: x,y,z')
    if command == 'item' or command == 'give':
        if len(args) == 3:
            id, count, slot = int(args[0]), int(args[1]), int(args[2])
            player.send_set_slot(id, count, slot)
        else:
            player.send_chat('3 args need')
    if command == 'help':
        player.send_chat('/tp [x, y, z]\n/stop\n/title line1 line2 2\n/give id count slot')
    if command == 'title':
        if len(args) == 3:
            player.send_title(args[0], args[1], 25, int(args[2]) * 25, 25)
        else: player.send_chat('3 args need')
    if command == 'brodcast' or command == 'bc':
        if len(args) == 0:
            player.send_chat('Enter your message')
        else:
            player.send_chat_all(''.join(args))
