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
            x, y, z = [float(arg) for arg in args]
            player.set_position(x, y, z)
            player.send_chat('Teleported to X:%s Y:%s Z:%s' % (x, y, z))
        else:
            player.send_chat('Need 3 args: x,y,z')
    if command == 'help':
        player.send_chat('/tppos [x, y, z]\n/stop')
    if command == 'brodcast':
        if len(args) == 0:
            player.send_chat('Enter your message')
        else:
            player.send_chat_all(''.join(args))