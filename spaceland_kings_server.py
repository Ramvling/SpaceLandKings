import sys
### myo-raw imports
sys.path.insert(0, './myo-raw')
from  myo import *

### PyWebPlug imports
import string, cgi, time
sys.path.insert(0, './PyWebPlug')
from wsserver import *
from time import sleep

import pygame
from pygame.locals import *
import badgl
import level
from OpenGL.GL import *


clients = []
pID = 0
serverTurn = False
readyClients = []
liveProjectiles = []
dead = []

def setupMessages():
    m1 = createMsgStruct(1, False)
    m1.addString()

    i1 = createMsgStruct(1, True)
    i1.addChars(2)

    test = createMsgStruct(2, False)
    test.addString()

    turn = createMsgStruct(3, True)
    turn.addChars(1)

    clientTurnOver = createMsgStruct(3, False)
    clientTurnOver.addChars(1)

    sendScore = createMsgStruct(4, True)
    sendScore.addString()

    sendHealth = createMsgStruct(5, True)
    sendHealth.addString()

    projectile = createMsgStruct(6, False)
    projectile.addString()

    gameOver = createMsgStruct(7, True)
    gameOver.addString()


class Client:
    def __init__(self, socket, pID):
        self.socket = socket
        self.pID = pID
        self.position = [0, 0, 0]
        self.square = badgl.SquareObject(1.0, 1.0, badgl.loadImage("dragon.bmp"))
        self.square.z = 1
        self.diamondillium = 0
        self.health = 100

    def hurt(self, damage):
        self.health -= damage
        self.socket.newPacket(5)
        self.socket.write(str(self.health))
        self.socket.send()       
        print("damage")

    def formatPosition(self):
        return ("(" + str(self.position[0]) + ',' + str(self.position[1]) + ',' + str(self.position[2]) + ")")
    

    def draw(self):
        self.square.x = self.position[0]
        self.square.y = self.position[1]
        self.square.z = self.position[2]
        self.square.draw()

    def handle(self, lvl):
        if self.health <= 0:
            self.socket.newPacket(7)
            self.socket.write("You are not the SpaceLand King")
            self.socket.send()
        
        #send score update
        self.socket.newPacket(4)
        self.socket.write(str(self.diamondillium) + ' ' + self.formatPosition())
        self.socket.send()

        global pID
        if (self.socket.canHandleMsg() == False):
            return
        packet = self.socket.readPacket()
        msgID = packet.msgID
        if msgID == 1:
            name = packet.read()
            self.confirm()

        if msgID == 2:
            dirrections = packet.read().split(" ")
            for dirr in dirrections:
                if (dirr == "Forward"):
                    self.position[1] += 1
                elif (dirr == "Backward"):
                    self.position[1] += -1
                elif (dirr == "Right"):
                    self.position[0] += 1
                elif (dirr == "Left"):
                    self.position[0] -= 1
                elif (dirr == "Up"):
                    self.position[2] += 1
                elif (dirr == "Down"):
                    self.position[2] += -1
                elif (dirr == "FireF"):
                    liveProjectiles.append(Projectile( 0.02, [0, 1, 0], 0.1, advance(self.position, (0,1,0)), 10))
                elif (dirr == "FireL"):
                    liveProjectiles.append(Projectile( 0.02, [-1, 0, 0], 0.1, advance(self.position, (-1,0,0)), 10))
                elif (dirr == "FireR"):
                    liveProjectiles.append(Projectile( 0.02, [1, 0, 0], 0.1, advance(self.position, (1,0,0)), 10))
                elif (dirr == "FireB"):
                    liveProjectiles.append(Projectile( 0.02, [0, -1, 0], 0.1, advance(self.position, (0,-1,0)), 10))


                self.position = lvl.in_bounds_it(self.position)
                lvl.events.runEvent(tuple(self.position), self)
            # since we don't need to do turn over naymore
            print("moving and appending to readyClients")
            readyClients.append(self)
            print(len(readyClients))
        if msgID == 3:
            print("messag id 3")
            readyClients.append(self)

    # Called to confirm to the client that the have been accepted, post sending us their details
    def confirm(self):
        self.socket.newPacket(1)
        self.socket.write(self.pID)
        self.socket.send()

    def disconnect(self):
        print("lost client")
        clients.remove(self)
        self.socket = None
        return

    def startTurn(self):
        self.socket.newPacket(3)
        self.socket.write('s')
        self.socket.send()
# this handles a new client
def handle(socket):
    global pID, clients
    pID += 1
    client = Client(socket, pID)
    clients.append(client)


def vecAdd(a,b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
def vecMult(a,b):
    return [a[0]*b,a[1]*b,a[2]*b]

class Projectile:
    square = None
    def __init__(self, speed, dirrection, size, position, damage):
        self.speed = speed
        self.dirrection = dirrection
        self.position = position
        self.size = size
        self.damage = damage
        self.dead = False
        self.timeout = 1.0
        if Projectile.square == None:
            Projectile.square = badgl.SquareObject(1.0, 1.0, badgl.loadImage("laser_ball.bmp"))

    def move(self):
            if not (self.dead):
                self.position = vecAdd(vecMult(self.dirrection, self.speed), self.position)
                #print(self.position);
                self.timeout -= 0.002
                if(self.timeout <= 0):
                    self.dead = True

    def collide(self, client):
        dist = (self.position[0] - client.position[0])**2 + (self.position[1] - client.position[1])**2 + (self.position[2] - client.position[2])**2
        dist = dist**0.5
        if (dist <= self.size):
            return True
        else:
            return False

    def draw(self):
        (Projectile.square.x, Projectile.square.y, Projectile.square.z) = self.position
        Projectile.square.draw()
        

class ServerPlayer:
    def __init__(self, moves, regen, health):
        self.position = [0,0,0]
        self.moves = moves
        self.regen = regen
        self.square = badgl.SquareObject(1.0, 1.0, badgl.loadImage("king_face.bmp"))
        self.health = health

    def draw(self):
        self.square.x = self.position[0]
        self.square.y = self.position[1]
        self.square.z = self.position[2]
        self.square.draw()

    def burstAttack(self):
        i = -1.0
        j = -1.0
        k = -1.0
        burst = []
        while (i < 1.0):
            while (j < 1.0):
                while(k <1.0):
                   burst.append(Projectile(0.1, [i,j,k], 0, [self.x,self.y,self.z], 1))   
                   k += 0.3
                j += 0.3
            i += 0.3

        liveProjectiles += burst    
    def hurt(self, damage):
        self.health -= damage
        print("hurt server")

def advance(pos, tup):
    return [pos[0] + tup[0], pos[1] + tup[1], pos[2] + tup[2]]

myo_pos_change = 11
def main():
    global readyClients
    game_over = False
    winner = None
    winning_score = 5

    if len(readyClients) == len(clients):
        serverTurn = True;
        print("server turn");
    badgl.make_and_setup_window(1000, 1000)

    server_player = ServerPlayer(10, 10, 200)
    server_player.z = 1
    
    lvl_size = 13
    lvl = level.Level(lvl_size, lvl_size, lvl_size, winning_score*2)
    lvl.z = -0.1
    quit = False
    global myo_pos_change
    myo_pos_change = 0

    global gameStarted
    global stage


    using_myo = False
    if (len(sys.argv) > 1):
        using_myo = True
        m = Myo(NNClassifier(), None)
        def handle_myo(it):
            global myo_pos_change
            print("handling fo")
            print(it)
            if (it == 0):
                myo_pos_change = 0
            elif it == 1:
                myo_pos_change = 1
            elif it == 2:
                myo_pos_change = -1
            elif it == 3:
                myo_pos_change = 1
            elif it == 4:
                myo_pos_change = 1
            else:
                it = 0
            print(myo_pos_change)
        m.add_raw_pose_handler(handle_myo)
        m.connect()

    try:
        setupMessages()
        server = startServer()
        count = 0
        while not quit:
            for e in pygame.event.get():
                if e.type == QUIT:
                    quit = True
            newClient = handleNetwork()
            if newClient:
                handle(newClient)
                print("New connection")
            all_dead = True if len(clients) > 0 else False
            winning_client = None
            for client in clients:
                client.handle(lvl)
                if client.health > 0:
                    all_dead = False
                if client.diamondillium >= winning_score:
                    winning_client = client
            if all_dead and winning_client == None:
                game_over = True
                winner = server_player
            elif winning_client != None:
                game_over = True
                winner = winning_client

            dead = []
            #projectiles loop
            for proj in liveProjectiles:
                proj.move()
                for entity in clients + [server_player]:
                    if proj.collide(entity) or (proj.dead):
                        if not proj.dead:
                            entity.hurt(proj.damage)
                        proj.dead = True
                        print("dead")
                        dead.append(proj)

            for proj in dead:
                if proj in liveProjectiles:
                    liveProjectiles.remove(proj)

            if len(readyClients) == len(clients) and not serverTurn:
                serverTurn = True;
                print("server turn on in while");
                print(len(readyClients))

            if using_myo:
                myo_pos_change = 0
                m.run()
                if serverTurn:
                    server_player.x += myo_pos_change
                #print(myo_pos_change)
            #else:
            key_map = pygame.key.get_pressed()
            if key_map[K_ESCAPE]:
                quit = True
            if serverTurn and count > 10:
                if server_player.health > 0:
                    if key_map[K_LEFT]:
                        server_player.position[0] += -1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_RIGHT]:
                        server_player.position[0] += 1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_UP]:
                        server_player.position[1] += 1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_DOWN]:
                        server_player.position[1] -= 1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_PAGEUP]:
                        server_player.position[2] += 1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_PAGEDOWN]:
                        server_player.position[2] -= 1
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_w]:
                        liveProjectiles.append(Projectile( 0.02, [0, 1, 0], 0.1, advance(server_player.position, (0,1,0)), 10))
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_a]:
                        liveProjectiles.append(Projectile( 0.02, [-1, 0, 0], 0.1, advance(server_player.position, (-1,0,0)), 10))
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_d]:
                        liveProjectiles.append(Projectile( 0.02, [1, 0, 0], 0.1, advance(server_player.position, (1,0,0)), 10))
                        server_player.moves -=1
                        count = 0
                    elif key_map[K_s]:
                        liveProjectiles.append(Projectile( 0.02, [0, -1, 0], 0.1, advance(server_player.position, (0,-1,0)), 10))
                        server_player.moves -=1
                        count = 0
                if key_map[K_SPACE] or server_player.moves <= 0:
                    print("end of server turn")
                    server_player.moves = server_player.regen
                    count = 0

                    serverTurn = False
                    for client in clients:
                        client.startTurn()
                    readyClients = []
                    print("at end of turn readyClients are")
                    print(readyClients)

                server_player.position = lvl.in_bounds_it(server_player.position)
            
            badgl.start_drawing()
            glTranslate(1, 1, -5)
            lvl.draw()
            for client in clients:
                client.draw()
            server_player.draw()
            for proj in liveProjectiles:
                proj.draw()
            glLoadIdentity()
            if game_over:
                if winner == server_player:
                    badgl.drawText((-0.95,0.85,-1), "THE SPACELAND KING WON")
                else:
                    badgl.drawText((-0.95,0.85,-1), "CROWN THE NEW SPACELAND KING:")
                    badgl.drawText((-0.95,0.75,-1), str(clients.index(winning_client)+1))
                badgl.end_drawing()
                while not (pygame.key.get_pressed()[K_ESCAPE] or pygame.key.get_pressed()[K_TAB]):
                    sleep(0.01)
                    #pass
                # time to reset everything
                for client in clients:
                    client.reset()
            else:
                if server_player.health > 0:
                    badgl.drawText((-0.95,0.85,-1), "WELCOME TO SPACELAND KINGS!")
                else:
                    badgl.drawText((-0.95,0.85,-1), "SPACELAND KING IS DEAD.")
                    badgl.drawText((-0.95,0.75,-1), "WHO WILL BE HIS SUCESSOR?!")
            badgl.end_drawing()
            #sleep(0.01)
            count += 1
            if (not count % 200):
                print(count)
    except KeyboardInterrupt:
        print(' recieved, closing server')
        server.close()
        raise

if __name__ == '__main__':
    main()




