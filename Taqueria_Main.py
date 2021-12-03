from os import name
from threading import Thread
import threading
import json
import boto3
#import queue
from time import sleep
import copy
import math
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from AWS.RoundRobin import SQS_handler
from AWS.tacos import orderGenerator
from visualizador.communicate import sendToNode
sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/292274580527/sqs_cc106_team_7"

OrdersInProcessDictionary= {}
STATES = ["REJECTED","READY","RUNNING","EXIT"] 
MEATS = ["asada", "adobada", "cabeza", "tripa", "suadero"]
TYPES = ["taco", "quesadilla"]
INGREDIENTS = ["salsa", "cilantro", "cebolla", "guacamole"]
CHALAN_WAITING_TIME = {"salsa":15, "cilantro":10, "cebolla":10, "guacamole":20, "tortillas":5}
INGREDIENTS_AT_MAX = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200, "tortillas":50}
TAQUERO_WAITING_TIME = {"salsa":0.5, "cilantro":0.5, "cebolla":0.5, "guacamole":0.5, "tortillas":0}
QUESADILLERO_STACK = 0

queueAdobada = deque()
queueAsadaSuadero = deque()
queueTripaCabeza = deque()
queueQuesadillas = deque()

cantSubordersInQOGH = 4   


class taqueroIndividual:
    def __init__(self, restTime, tacosNeededForRest, id, fan = False, stackQuesadillas = 5):
        self.fillings = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200, "tortillas":50}
        self.stackQuesadillas = stackQuesadillas
        self.fan = fan
        self.id = id
        self.flag = False
        self.restTime = restTime
        self.tacoCounter = 0
        self.tacosNeededForRest = tacosNeededForRest

    def fan_(self):
        if (self.tacoCounter % 600 == 0):
            return True
        return False
        
    def rest(self):
        if(self.tacoCounter % self.tacosNeededForRest == 0):
            sleep(self.restTime)
            return True
        return False

class queues:
    def __init__(self):
        self.QOP = deque()
        self.QOGE = deque()
        self.QOGH = deque()

class taquerosShared:
    def __init__(self, restTime1, restTime2, id1, id2):
        self.taquero1 = taqueroIndividual(restTime1, 311, id1)
        self.taquero2 = taqueroIndividual(restTime2, 313, id2)
        queues.__init__(self)

class taco:
    def __init__(self, quantity, tacoDuration) -> None:
        self.quantity = quantity
        self.tacoDuration = tacoDuration

def fanHandler(instance):
    # deberia de ser un thread 
    if (instance.fan_()):
        instance.fan = True
        sleep(60)
        instance.fan = False
    

def checkIfEmpty(suborderList):
    return len(suborderList)==0

def assignToTaqueroQueue(suborder, key):
    orden = OrdersInProcessDictionary[key]
    who = "Categorizador"
    
    indexAd = MEATS.index('adobada')
    indexAs = MEATS.index('asada')
    indexTr = MEATS.index('tripa')
    indexCa = MEATS.index('cabeza')
    indexSu = MEATS.index('suadero')


    # Si carne de tacos de la suborder es tripa o cabeza
    if(suborder['meat'] == MEATS[indexTr] or suborder['meat'] == MEATS[indexCa]):
        #AGREGAR suborder al queue del taquero de tripa y cabeza
        queueTripaCabeza.append(suborder)
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Tripa y Cabeza".format(suborder['part_id']))
        globalAssignator(queueTripaCabeza, taqueroTripaCabeza)
    # Si carne de tacos de la suborder es asada o suadero    
    if(suborder['meat'] == MEATS[indexAs] or suborder['meat'] == MEATS[indexSu]):
        #AGREGAR suborder al queue de los taqueros de asada
        queueAsadaSuadero.append(suborder)
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Asada y suadero".format(suborder['part_id']))
        globalAssignator(queueAsadaSuadero, taqueroAsadaSuadero)
    # Si carne de tacos de la suborder es adobada    
    if(suborder['meat'] == MEATS[indexAd]):
        #AGREGAR suborder al queue de Adobada
        queueAdobada.append(suborder)
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Adobada".format(suborder['part_id']))
        globalAssignator(queueAdobada, taqueroAdobada)

lockMaxSum = threading.Lock()
def maxSumOrder(orden, maxQuantity, key, type):
    lockMaxSum.acquire()
    ordenCompleta = OrdersInProcessDictionary[key]
    isTaco = lambda x: x['type'] == TYPES[type]
    #print(orden,sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ), type)
    if sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ) > maxQuantity:
        OrdersInProcessDictionary[key]['status'] = STATES[0]
        responseOrden(key, ordenCompleta, "Categorizador", "Rechazó orden (Cantidad total excede el limite aceptado)")
        for suborder in orden:
            suborder['status'] = STATES[0]
        lockMaxSum.release()
        return True
    lockMaxSum.release()
    return False


def calcularMS(DateLlegada, DateAccion):
    from dateutil import parser
    date1 = parser.parse(str(DateAccion))
    date2 = parser.parse(DateLlegada)
    ms = int((date1 - date2).total_seconds() * 1000)
    return ms

def responseOrden(key, orden, who, what):
    OrdersInProcessDictionary[key]['response'].append({
        "Who" : who,
        "When" : str(datetime.now()) ,
        "What" : what,
        "Time" : calcularMS(orden['datetime'], datetime.now())
        })

lockCategorizar = threading.Lock()
def categorizador(ordenCompleta,key): # objeto de toda la orden
    
    who = "Categorizador"

    lockCategorizar.acquire()
    orden = ordenCompleta['orden']
    minQuantityPerSuborder = 1
    maxQuantityPerSuborderTacos = 100
    maxQuantityPerSuborderQuesadillas = 50
    maxQuantityPerOrderTacos = 400
    maxQuantityPerOrderQuesadillas = 100
    OrdersInProcessDictionary[key]['response'] = []
    # ESTADOS: REJECTED (0)| READY (1) | RUNNING (2)| EXIT (3)
    # Check if order is empty
    if checkIfEmpty(orden): 
        OrdersInProcessDictionary[key]['status'] = STATES[0]
        responseOrden(key, ordenCompleta, who, "Rechazó orden (orden vacía)")


    # suborderes: no empty, 100 > tacos en suborder, 400 > tacos en total de orden
    flag = maxSumOrder(orden, maxQuantityPerOrderQuesadillas, key, 1)
    flag = maxSumOrder(orden, maxQuantityPerOrderTacos, key, 0)
    if flag:
        return
    for suborder in orden:

        # Check if type is supported
        index = len(suborder['part_id'].split('-')[1])
        suborderIndex = int(suborder['part_id'][-index:])
        if suborder['type'] not in TYPES: 
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
            responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No existe el tipo)".format(suborder['part_id']))
            continue
        
        if suborder['type'] == TYPES[0]:#taco
            # Check min and max of suborder
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderTacos: 
                OrdersInProcessDictionary[key]['orden'][ suborderIndex ]['status'] = STATES[0]
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (Cantidad excede el limite de tacos)".format(suborder['part_id']))
                continue
        else:
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderQuesadillas: 
                OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (Cantidad excede el limite de quesadillas)".format(suborder['part_id']))
                continue
        # Check if meat is supported
        if suborder['meat'] not in MEATS: 
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
            responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No acepta esa carne)".format(suborder['part_id']))
            continue
        
        # Check if ingredients are supported
        for ingredient in suborder['ingredients']:
            if ingredient not in INGREDIENTS: 
                OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No acepta el ingrediente)".format(suborder['part_id']))
                break

        #print(suborder['part_id'], suborder['type'], suborder['meat'], suborder['quantity'])
        if(suborder['status'] != STATES[0]):
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['remaining_tacos'] = OrdersInProcessDictionary[key]['orden'][suborderIndex]['quantity']
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[1]
            responseOrden(key, ordenCompleta, who, "La suborden {0} entra en estado READY".format(suborder['part_id']))
            assignToTaqueroQueue(suborder, key)

    lockCategorizar.release()

lockAsign = threading.Lock()
def globalAssignator(queueNeeded, taqueroInstance):
    who = "Asignador Global"
    # dequeue del queue global
    suborder = queueNeeded.pop()
    key = int(suborder['part_id'].split('-')[0])
    # enqueue al queue correpondiente del taquero
    # quantity, type
    # TACOS Y QUESADILLAS
    lockAsign.acquire()
    where = None
    if(suborder['quantity'] <= 25):
        while lockInutil.locked()==True:
            pass
        taqueroInstance.QOP.append(suborder)
        where = 'QOP'
        #print("QOP",taqueroInstance.__dict__['QOP'].pop())
    else:
        if(len(taqueroInstance.QOGE)==0):
            if(len(taqueroInstance.QOGH) == 4):
                while lockInutil.locked()==True:
                    pass
                taqueroInstance.QOGE.append(suborder) 
                where = 'QOGE'
                #print("QOGE",taqueroInstance.__dict__['QOGE'].pop())   
            else:
                while lockInutil.locked()==True:
                    pass
                taqueroInstance.QOGH.append(suborder)
                where = "QOGH"
                #print("QOGH",taqueroInstance.__dict__['QOGH'].pop())
        else:
            while lockInutil.locked()==True:
                pass
            taqueroInstance.QOGE.append(suborder)  
            where = 'QOGE'  
            #print("QOGE",taqueroInstance.__dict__['QOGE'].pop())
    name = taqueroInstance.__class__.__name__
    responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} agregada a {1} de taquero {2}".format(suborder['part_id'],where, name))
    lockAsign.release()

lockQuesa = threading.Lock()
def quesadillero():
    global currentQuesadilla
    who = 'quesadillero'
    while True:
        # NOTA: Va a funcionar como un FIFO?
        # AGREGAR STACK
        if (queueQuesadillas):
            suborden = queueQuesadillas.pop()
            index = len(suborden[0]['part_id'].split('-')[1])
            index = int(suborden[0]['part_id'][-index:])
            # llave de la orden a la que pertenece
            key = int(suborden[0]['part_id'].split('-')[0])

            if (suborden[2]):
                responseOrden(key, OrdersInProcessDictionary[key], who, "Comienza a hacer {0} quesadillas para taquero {1}".format(suborden[0]['quantity'], suborden[1]))
            else:    
                responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} comienza a hacerse".format(suborden[0]['part_id']))
            # notificar que sta haciendo quesadilla 'tal'
            # SLEEEEEEEEEEEEP
            if (not suborden[2]):
                print("Quesadillero haciendo suborden de quesadillas {0}".format(suborden[0]['part_id']))
            for quesadillaCount in range(suborden[0]['quantity']):
                sleep( 2 )
                if (not suborden[2]):
                    currentQuesadilla = [suborden[0]['part_id'], suborden[0]['quantity'] - quesadillaCount, len(queueQuesadillas)]
            currentQuesadilla = []
            if (not suborden[2]):
                print("Quesadillero ha terminado")
                info.pop(suborden[0]['part_id'])
            # indice para identificar a la suborden dentro del diccionario
            # poner estado de suborden como exit
            OrdersInProcessDictionary[key]['orden'][index]['status'] = STATES[3]
            if (suborden[2]):
                responseOrden(key, OrdersInProcessDictionary[key], who, "Termina a hacer {0} quesadillas para taquero {1}".format(suborden[0]['quantity'], suborden[1]))
                dispatcher(suborden, key)
            else: 
                responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} hecha".format(suborden[0]['part_id']))
                mergeFinishedOrders(key)
                
def dispatcher(suborden, key): # suborden es una tupla (sub , taquero.id, 0)
    who = "Dispatcher"
    # adobada 0, taquero1 =1, taquero2=2, tripa 3
    # Se encargara de unir las subordenes 
    
    # check taquero id y a su atributo stackQuesadillas += sub['quantity']

    if suborden[1] == 0:
        taqueroAdobada.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 1:
        taqueroAsadaSuadero.taquero1.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 2:
        taqueroAsadaSuadero.taquero2.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 3:
        taqueroTripaCabeza.stackQuesadillas += suborden[0]['quantity']
    print("despachando orden", suborden[0]['part_id'])
    responseOrden(key, OrdersInProcessDictionary[key], who, "{0} quesadillas agregadas a stack de taquero {1}".format(suborden[0]['quantity'], suborden[1]))
    
lockInutil = threading.Lock()
lockGetKeys = threading.Lock()
def individualTaqueroMethod(taquero):

    who = "Taquero " + str(taquero.id)
    print(taquero.QOP)
    while(True):
        # NOTA 2.0 Cuando llegue una suborden de quesadillas, se le tratará como taco (poniendole ingredientes y carne)
        #   y se enviará al quesadillero para que el ponga su quesito y no tenga que regresarlo al tqeuro de nuevo.    
        while lockAsign.locked()==True:
            pass
        if (len(taquero.QOP)>0):
            lockInutil.acquire()
            sub = taquero.QOP.pop()
            lockInutil.release()
        # CAMBIAR ESTO POR UN SOLO POP POR VEZ?
        #for sub in snapshotQOP:
        # indice para identificar a la suborden dentro del diccionario
            index = len(sub['part_id'].split('-')[1])
            subordenIndex = int(sub['part_id'][-index:])
            # llave de la orden a la que pertenece
            key = int(sub['part_id'].split('-')[0])
            ordenCompleta = OrdersInProcessDictionary[key]
            responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOP)".format(sub['part_id']))
            stackTaken = False
            if (sub['type']==TYPES[1]):
                if (sub['quantity'] <= taquero.stackQuesadillas):
                    # darle las quesadillas
                    taquero.stackQuesadillas -= sub['quantity']
                    #taquero.stackQuesadillas += sub['quantity'] # temporal cheat code [infinite quesadillas in stack]
                    peticionQuesadillas = (sub , taquero.id, 1)
                    queueQuesadillas.append(peticionQuesadillas)  #quesadillas dispatcher que el va usar IDS y todo eso 
                    stackTaken = True
            # llamar a pedir las quesadillas que se van a utilizar
            # se itera por cada taco en la suborden de quesadillas
            for taco in range(sub['quantity']):
                # se hace cada taco
                cookFood(taquero, sub, key, subordenIndex)
                info[sub['part_id']] = [sub["part_id"], sub["type"], sub["meat"], sub["remaining_tacos"]]
                sendMetadata()
                if taquero.rest():
                    # Si el taquero si descanso agregarlo como accion en nuestra Respuesta
                    responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(taquero.id))
            if sub['type']==TYPES[1] and stackTaken == False:
                peticionQuesadillas = (sub , taquero.id, 0)
                queueQuesadillas.append(peticionQuesadillas)
                responseOrden(key, ordenCompleta, who, "Suborden {0} enviada a quesadillero (QOP)".format(sub['part_id']))
            else:
                info.pop(sub['part_id'])
                responseOrden(key, ordenCompleta, who, "Suborden {0} es completada (QOP)".format(sub['part_id']))
                OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                mergeFinishedOrders(key)
            print("done")
            
        # acquire( Taquero.QOP )
        # release bla 
        for i in range(cantSubordersInQOGH):
            if len(taquero.QOGH)>0:
                # Logica de preparacion de cada taco de cada suborden grande dentro del QOGH
                subordenG = taquero.QOGH.pop()
                
                lockGetKeys.acquire()
                index = len(subordenG['part_id'].split('-')[1])
                subordenIndex = int(subordenG['part_id'][-index:])
                key = int(subordenG['part_id'].split('-')[0])
                ordenCompleta = OrdersInProcessDictionary[key]
                lockGetKeys.release()
                responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOGH)".format(subordenG['part_id']))
                cantTacosPorHacer = math.floor(subordenG['quantity'] / 4)
                # En base al siguiente condicional aseguramos que cada suborden siempre sea completada en exactamente 4 repeticiones
                if(OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] / cantTacosPorHacer < 2):
                    cantTacosPorHacer = OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos']

                # Por aqui va lo de agregar RUNNING al diccionario de los estados
      
                for tacos in range(cantTacosPorHacer): 
                    cookFood(taquero, subordenG, key, subordenIndex )
                    info[subordenG['part_id']] = [subordenG["part_id"], subordenG["type"], subordenG["meat"], subordenG["remaining_tacos"]]
                    sendMetadata()
                    if taquero.rest(): # Esta funcion se llama y el taquero decide si es momento de descansar en base a la cantidad de tacos que lleva
                        responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(taquero.id))

                # Logica de actualizacion de diccionario y revision de subordenes grandes completadas
                if (OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] == 0):
                    if subordenG['type'] == TYPES[TYPES.index('quesadilla')]:
                        subordenQues = (subordenG, taquero.id, 0)
                        queueQuesadillas.append(subordenQues)
                        
                    else:
                        info.pop(subordenG['part_id'])
                        OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                        responseOrden(key, ordenCompleta, who, "Suborden {0} es completada".format(subordenG['part_id']))
                        mergeFinishedOrders(key)
                    if (len(taquero.QOGE)>0):
                        taquero.QOGH.append(taquero.QOGE.pop())
                else:
                    taquero.QOGH.append(subordenG)

i = 0

lockHacerTaco = threading.Lock()
def cookFood(taquero, suborder, key, subordenIndex):
    global i
    who = "taquero" + str(taquero.id)
    # Sleep default por hacer un taco
    print(f"{who} haciendo un taco de {suborder['part_id']}, la taqueria lleva: {i+1}")
    i+=1

    # El taquero se tarda 1 segundo en hacer un taco
    sleep(1)
    # Variables necesarias para actualizar las acciones de la orden
    lockHacerTaco.acquire()
    # Objeto que representa la orden padre de la suborden actual
    ordenCompleta = OrdersInProcessDictionary[key]

    #print(list(OrdersInProcessDictionary[key]['orden'][abs( int(suborder['part_id'][-(index):]))].keys()))
    
    # Boolenao que limita la cantidad de responses agregadas al diccionario en espera de ingrediente rellenado por el chalan
    First = False
    while(taquero.fillings['tortillas'] == 0):
        # En caso de que no se tengan tortillas el taquero se espera en este while hasta que se rellenen
        if (First==False):
            responseOrden(key, ordenCompleta, who, "Suborden {0} en espera de tortillas".format(suborder['part_id']))
            First = True
    # Resta de los fillings que contiene el taco y en caso de que no se tengan fillings el taquero se espera a que sean rellenados
    for ing in suborder['ingredients']:
        First = False
        while (taquero.fillings[ing] == 0):
            if (First==False):
                responseOrden(key, ordenCompleta, who, "Suborden {0} en espera de que el chalan rellene ingrediente {1}".format(suborder['part_id'], ing))
                First = True
        # SLEEP INGREDIENTE!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #sleep(TAQUERO_WAITING_TIME[ing])  
        taquero.fillings[ing] -= 1
    
    # Siempre que el taquero hace un taco se utiliza una tortilla y el counter del taquero incrementa
    taquero.fillings["tortillas"] -=1        
    taquero.tacoCounter += 1
    
    # Restamos la cantidad de restantes de tacos por uno
    OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] -=1
    info[suborder['part_id']] = [suborder["part_id"], suborder["type"], suborder["meat"], suborder["remaining_tacos"]]
    lockHacerTaco.release()

parallel_on_same_queue = threading.Lock()
parallel_on_different_queues = threading.Lock()
quesadillasLock = threading.Lock()
change_flag = threading.Lock()
parallel_on_same_queue_QOGH = threading.Lock()
appendQOGH = threading.Lock()
cookGrande = threading.Lock()
cookPeque = threading.Lock()

def sharedTaqueroMethod(Taquero, instance):
    stackTaken = {1: False, 2: False}
    while (True):    
        who = "Taquero {0}".format(instance.id)
        if parallel_on_different_queues.locked() == False:
            # <-- LOCKING
            if (len(Taquero.QOGH) > 0):
                parallel_on_different_queues.acquire()
                change_flag.acquire()
                # checar que taquero soy 
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == False):
                        instance.flag = True
                else:
                    if (Taquero.taquero1.flag == False):
                        instance.flag = True
                change_flag.release()
            #print(f"{who} esta aqui con {instance.flag} y  longitud {len(Taquero.QOP) }")
            while(len(Taquero.QOP) > 0 and instance.flag == False):
                print(f"{who} hace orden pequeña")
                parallel_on_same_queue.acquire() # cuando tome algo del qop hago antes un acquire
                subordenP = None
                if len(Taquero.QOP)>0:
                    subordenP = Taquero.QOP.pop()
                parallel_on_same_queue.release() # cuando ya lo tenga le hago release para que el otro tome la siguiente orden pequenia
                # toda la logica de hacer la suborden
                # indice para identificar a la suborden dentro del diccionario
                if (subordenP is not None):
                    index = len(subordenP['part_id'].split('-')[1])
                    subordenIndex = int(subordenP['part_id'][-index:])
                    # llave de la orden a la que pertenece
                    key = int(subordenP['part_id'].split('-')[0])
                    ordenCompleta = OrdersInProcessDictionary[key]
                    responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOP)".format(subordenP['part_id']))
                    quesadillasLock.acquire()
                    if (subordenP['type']==TYPES[1]):
                        if (subordenP['quantity'] <= instance.stackQuesadillas):
                            instance.stackQuesadillas -= subordenP['quantity']
                            peticionQuesadillas = (subordenP , instance.id, 1)
                            queueQuesadillas.append(peticionQuesadillas)
                            stackTaken[instance.id] = True
                    quesadillasLock.release()
                    print("Suborden {0} en proceso (QOP)".format(subordenP['part_id']))
                    for taco in range(subordenP['quantity']):
                        # se hace cada taco
                        cookPeque.acquire()
                        cookFood(instance, subordenP, key, subordenIndex)
                        info[subordenP['part_id']] = [subordenP["part_id"], subordenP["type"], subordenP["meat"], subordenP["remaining_tacos"]]
                        sendMetadata()
                        if instance.rest(): # El taquero que haya hecho el taco revisa si es necesario descansar
                            responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(instance.id))
                        cookPeque.release()
                    quesadillasLock.acquire()
                    if subordenP['type']==TYPES[1] and stackTaken == False:
                        peticionQuesadillas = (subordenP , instance.id, 0)
                        queueQuesadillas.append(peticionQuesadillas)
                        responseOrden(key, ordenCompleta, who, "Suborden {0} enviada a quesadillero (QOP)".format(subordenP['part_id']))
                    else:
                        responseOrden(key, ordenCompleta, who, "Suborden {0} es completada (QOP)".format(subordenP['part_id']))
                        OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                        info.pop(subordenP['part_id'])
                        mergeFinishedOrders(key)
                    quesadillasLock.release()
                    if len(Taquero.QOGH) > 0: # Si de la nada llegó una orden grande 
                        
                        change_flag.acquire()
                        if(Taquero.taquero1 == instance):
                            if (Taquero.taquero2.flag == False):
                                instance.flag = True
                        else:
                            if (Taquero.taquero1.flag == False):
                                instance.flag = True
                        #instance.flag = True
                        change_flag.release()    
            if len(Taquero.QOGH) > 0: # Si de la nada llegó una orden grande 
                    
                change_flag.acquire()
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == False):
                        instance.flag = True
                else:
                    if (Taquero.taquero1.flag == False):
                        instance.flag = True
                #instance.flag = True
                change_flag.release()    
            else:
                #print("QOP empty") 
                change_flag.acquire()
                instance.flag = False
                change_flag.release() 
                
        # <-- UNLOCKING
        else: 
            print(f"{who} is at QOGH {len(Taquero.QOGH)}, {instance.flag}")
            if (len(Taquero.QOGH) > 0 and instance.flag == True):
                print(f"----------{who} hace orden grande----------------")
                parallel_on_same_queue_QOGH.acquire()
                # si len(Taquero.QOGH) == 0 el otro taquero se sale del if deberia hacer pop
                subordenG = None
                if (len(Taquero.QOGH) > 0):
                    subordenG =  Taquero.QOGH.pop()
                parallel_on_same_queue_QOGH.release()
                if (subordenG is not None):
                    index = len(subordenG['part_id'].split('-')[1])
                    subordenIndex = int(subordenG['part_id'][-index:])
                    key = int(subordenG['part_id'].split('-')[0])
                    ordenCompleta = OrdersInProcessDictionary[key]
                    responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOGH)".format(subordenG['part_id']))
                    cantTacosPorHacer = math.floor(subordenG['quantity'] / 8)
                    if(OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] / cantTacosPorHacer < 2):
                        cantTacosPorHacer = OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos']

                    for tacos in range(cantTacosPorHacer): 
                        cookGrande.acquire()
                        cookFood(instance, subordenG, key, subordenIndex)
                        info[subordenG['part_id']] = [subordenG["part_id"], subordenG["type"], subordenG["meat"], subordenG["remaining_tacos"]]
                        sendMetadata()
                        if instance.rest(): # El taquero que haya hecho el taco revisa si es necesario descansar
                            responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(instance.id))
                        cookGrande.release()
                        if (len(Taquero.QOP)>0):
                            change_flag.acquire()
                            if(Taquero.taquero1 == instance):
                                if (Taquero.taquero2.flag == True):
                                    instance.flag = False
                                    if parallel_on_different_queues.locked():
                                        parallel_on_different_queues.release()
                            else:
                                if (Taquero.taquero1.flag == True):
                                    instance.flag = False
                                    if parallel_on_different_queues.locked():
                                        parallel_on_different_queues.release()
                            #instance.flag = True
                            change_flag.release()
                    appendQOGH.acquire()
                    if (OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] == 0):
                        if subordenG['type'] == TYPES[TYPES.index('quesadilla')]:
                            subordenQues = (subordenG, instance.id, 0)
                            queueQuesadillas.append(subordenQues)
                            
                        else:
                            info.pop(subordenG['part_id'])
                            OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                            responseOrden(key, ordenCompleta, who, "Suborden {0} es completada".format(subordenG['part_id']))
                            mergeFinishedOrders(key)
                        if (len(Taquero.QOGE)>0):
                            print(f"QOGE -----> QOGH  {len(Taquero.QOGE)}")
                            Taquero.QOGH.append(Taquero.QOGE.pop())
                    else:
                        print(f"subordenG -----> QOGH, restantes: {OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] }")
                        
                        Taquero.QOGH.append(subordenG)  
                    appendQOGH.release()
            #if (len(Taquero.QOP)>0):
            if (len(Taquero.QOP)>0):
                change_flag.acquire()
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == True):
                        instance.flag = False
                        if parallel_on_different_queues.locked():
                            parallel_on_different_queues.release()
                else:
                    if (Taquero.taquero1.flag == True):
                        instance.flag = False
                        if parallel_on_different_queues.locked():
                            parallel_on_different_queues.release()
                #instance.flag = True
                change_flag.release()  
            else:
                #print("QOP empty") 
                change_flag.acquire()
                instance.flag = True
                change_flag.release()  
            if parallel_on_different_queues.locked():   
                parallel_on_different_queues.release()
                #instance.flag = False
        # QOP      
        # taquero.FLAG si un taquero esta haciendo ordenes pequenias
            # SI HAY ALGUIEN
                # ESE TAQUERO SE ENCARGA DE CONTINUAR SACANDO COSAS DEL QOP Y HACIENDOLAS
                # SI EL QOP ESTA VACIO SE CAMBIA SU FLAG PARA HACER ORDENES DEL QOGH
            # NO HAY NADIE
                # SE ESPERA LA ORDEN A QUE ALGUNO DE LOS DOS TAQUEROS TERMINE DE HACER SU OCTAVO Y A DICHO
                #    TAQUERO SE LE ASIGNA EL FLAG DE HACER LAS ORDENES PEQUENIAS


#El chalán rellenará primero el cilantro seguido por la cebolla, el guacamole y por último la salsa.
# checar tortillas < 50
# tortillas, guacamole, salsa, cebolla, cilantro
# CHALAN_WAITING_TIME = {"salsa":15, "cilantro":10, "cebolla":10, "guacamole":20, "tortillas":5}

def chalanArriba():
    # este bato va a ser explotado laboralmente C:
    # el tiempo de rellenado de los ingredientes es proporcional a la cantidad de ingredientes por rellenar?
    # Ejemplo: (si rellena 5 tortillas el tiempo es 5 segundos aun asi? o si es proporcional)
    
    # Diccionario con fillings de todos los taqueros
    
    #fillingsList[0].pop(fillingsList[0].index(min(fillingsList[0])))
    # Ordenar de menor a mayor y rellenar?
    
    while True:
        ingredientsA = [(taqueroAdobada.fillings[ingredient],i) for ingredient,i in zip(list(taqueroAdobada.__dict__['fillings']), range(0,5))]
        ingredientsS = [(taqueroAsadaSuadero.taquero1.fillings[ingredient],i) for ingredient,i in zip(list(taqueroAsadaSuadero.taquero1.__dict__['fillings']), range(0,5))]
        fillingsList = [ingredientsA,ingredientsS]
        #fillingsList[0].extend(ingredientsA)
        #fillingsList[1].extend(ingredientsS)
        fillingsList[0] = [ (porcentaje(tupleInfo[0], fillingsList[0].index(tupleInfo)), tupleInfo[1]) for tupleInfo in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(tupleInfo[0], fillingsList[1].index(tupleInfo)), tupleInfo[1]) for tupleInfo in fillingsList[1] ]
        if min(fillingsList[0]) >= min(fillingsList[1]):
            do = min(fillingsList[1])
            if do[0] < 1.0:
                
                which = list(taqueroAsadaSuadero.taquero1.__dict__['fillings'])[do[1]]
                taqueroAsadaSuadero.taquero1.fillings[which] = INGREDIENTS_AT_MAX[which]
                # PREGUNTAR SI TENEMOS QUE NOTIFICAR
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero1.id))
                sleep(CHALAN_WAITING_TIME[which])
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero1.id))
                sendMetadata()
        else:
            do = min(fillingsList[0])
            if do[0] < 1.0: 
                which = list(taqueroAdobada.__dict__['fillings'])[do[1]]
                taqueroAdobada.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAdobada.id))
                sleep(CHALAN_WAITING_TIME[which])
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAdobada.id))
                sendMetadata()
            
def chalanAbajo():
    
    while True:
        ingredientsT = [(taqueroTripaCabeza.fillings[a],i) for a,i in zip(list(taqueroTripaCabeza.__dict__['fillings']), range(0,5))]
        ingredientsS= [(taqueroAsadaSuadero.taquero2.fillings[a],i) for a,i in zip(list(taqueroAsadaSuadero.taquero2.__dict__['fillings']), range(0,5))]
        fillingsList = [ingredientsT, ingredientsS]
        #fillingsList[0].extend(ingredientsT)
        #fillingsList[1].extend(ingredientsS)
        fillingsList[0] = [ (porcentaje(a[0], fillingsList[0].index(a)), a[1]) for a in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(a[0], fillingsList[1].index(a)), a[1]) for a in fillingsList[1] ]
        if min(fillingsList[0]) >= min(fillingsList[1]):
            do = min(fillingsList[1])
            if do[0] < 1.0:
                
                which = list(taqueroAsadaSuadero.taquero2.__dict__['fillings'])[do[1]]
                taqueroAsadaSuadero.taquero2.fillings[which] = INGREDIENTS_AT_MAX[which]
                # PREGUNTAR SI TENEMOS QUE NOTIFICAR
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero2.id))
                sleep(CHALAN_WAITING_TIME[which])
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero2.id))
                sendMetadata()
        else:
            do = min(fillingsList[0])
            if do[0] < 1.0:
                
                which = list(taqueroTripaCabeza.__dict__['fillings'])[do[1]]
                taqueroTripaCabeza.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroTripaCabeza.id))
                sleep(CHALAN_WAITING_TIME[which])
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroTripaCabeza.id))
                sendMetadata()
       
joinear = []

def mergeFinishedOrders(keyOrdenPadre):
    # recibimos una key de la suborden que ha sido finalizada
    # queremos revisar el papa y revisar que todos sus hijos esten en estado EXIT
    # si todos estan en EXIT el estado del papa se cambia tambien a EXIT, fin
    objetoOrden = OrdersInProcessDictionary[keyOrdenPadre]
    ordenCompleta = objetoOrden['orden']
    #isExit = lambda x: x['status'] == STATES[3]
    #print(orden,sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ), type)
    if all([ x['status'] == STATES[3] for x in ordenCompleta] ) :
        OrdersInProcessDictionary[keyOrdenPadre]['status'] = STATES[3]
        with open('response.json', 'w') as f:
            json.dump(OrdersInProcessDictionary, f)
        print('<<<<<<<<<< Orden {0} terminada >>>>>>>>>>'.format(objetoOrden['request_id']))
        # ESTO NO VA COMENTADO
        # POR AHORA LO COMENTO PARA NO TENER MENSAJES NO VISIBLES EN EL QUEUE SI HAY ERRORES
        # DURANTE EL RUNTIME
        
        #handler.delete_message(objetoOrden['message'], objetoOrden, sqs, queue_url)

def readJson(message, orden):
    #orden['message'] = message['Message']
    OrdersInProcessDictionary[orden['request_id']] = orden
    
    #orden_thread = Thread(tarpop=categorizador, args=(ordenObject, orden['request_id']))
    #i+=1  
    #joinear.append(orden_thread)
    #orden_thread.start()
    categorizador(orden, orden['request_id'])
    
sqsLock = threading.Lock()

def cliente1():
    while True:
        msg, orden = handler.read_message(sqs, queue_url)
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            sqsLock.acquire()
            readJson(msg, orden)
            sqsLock.release()

def cliente2():
    while True:
        msg, orden = handler.read_message(sqs, queue_url)
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            sqsLock.acquire()
            readJson(msg, orden)
            sqsLock.release()

def cliente3():
    while True:
        msg, orden = handler.read_message(sqs, queue_url)
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            sqsLock.acquire()
            readJson(msg, orden)
            sqsLock.release()
def sendMetadata():
    data = { "0":[taqueroAdobada.id, taqueroAdobada.tacoCounter, taqueroAdobada.fillings["salsa"], taqueroAdobada.fillings["guacamole"], taqueroAdobada.fillings["cebolla"], taqueroAdobada.fillings["cilantro"], taqueroAdobada.fillings["tortillas"], taqueroAdobada.stackQuesadillas, taqueroAdobada.fan, taqueroAdobada.tacoCounter%taqueroAdobada.tacosNeededForRest == 0 ],
    "1":[taqueroAsadaSuadero.taquero1.id, taqueroAsadaSuadero.taquero1.tacoCounter, taqueroAsadaSuadero.taquero1.fillings["salsa"], taqueroAsadaSuadero.taquero1.fillings["guacamole"], taqueroAsadaSuadero.taquero1.fillings["cebolla"], taqueroAsadaSuadero.taquero1.fillings["cilantro"], taqueroAsadaSuadero.taquero1.fillings["tortillas"], taqueroAsadaSuadero.taquero1.stackQuesadillas, taqueroAsadaSuadero.taquero1.fan, taqueroAsadaSuadero.taquero1.tacoCounter%taqueroAsadaSuadero.taquero1.tacosNeededForRest == 0 ],
    "2":[taqueroAsadaSuadero.taquero2.id, taqueroAsadaSuadero.taquero2.tacoCounter, taqueroAsadaSuadero.taquero2.fillings["salsa"], taqueroAsadaSuadero.taquero2.fillings["guacamole"], taqueroAsadaSuadero.taquero2.fillings["cebolla"], taqueroAsadaSuadero.taquero2.fillings["cilantro"], taqueroAsadaSuadero.taquero2.fillings["tortillas"], taqueroAsadaSuadero.taquero2.stackQuesadillas, taqueroAsadaSuadero.taquero2.fan, taqueroAsadaSuadero.taquero2.tacoCounter%taqueroAsadaSuadero.taquero2.tacosNeededForRest == 0 ],
    "3":[taqueroTripaCabeza.id, taqueroTripaCabeza.tacoCounter, taqueroTripaCabeza.fillings["salsa"], taqueroTripaCabeza.fillings["guacamole"], taqueroTripaCabeza.fillings["cebolla"], taqueroTripaCabeza.fillings["cilantro"], taqueroTripaCabeza.fillings["tortillas"], taqueroTripaCabeza.stackQuesadillas, taqueroTripaCabeza.fan, taqueroTripaCabeza.tacoCounter%taqueroTripaCabeza.tacosNeededForRest == 0]}
    sendToNode(data, info, currentQuesadilla)
# adobada =0, taquero1 =1, taquero2=2, tripa 3
handler = SQS_handler()
orderGen = orderGenerator()
instanceQueues = queues()
taqueroAdobada = taqueroIndividual(3, 100, 0)
taqueroTripaCabeza = taqueroIndividual(3, 100, 3)
taqueroAsadaSuadero = taquerosShared(9.33, 9.39, 1, 2)
taqueroAdobada.__dict__.update(instanceQueues.__dict__)
instanceQueues = queues()
taqueroTripaCabeza.__dict__.update(instanceQueues.__dict__)
info = {}
currentQuesadilla = []

def porcentaje(a,b):
    return a / INGREDIENTS_AT_MAX[list(INGREDIENTS_AT_MAX.keys())[b]]

if __name__ == "__main__":
    chalanArribaThread = Thread(target=chalanArriba, args=())
    chalanAbajoThread = Thread(target=chalanAbajo, args=())
    quesas = Thread(target=quesadillero, args=())
    sqs_listener1 = Thread(target=cliente1, args=())
    sqs_listener2 = Thread(target=cliente2, args=())
    sqs_listener3 = Thread(target=cliente3, args=())
    #visual = Thread(target=sendMetadata, args=())
    #printJson = Thread(target=mergeFinishedOrders, args=())
    
    # funciones test
    #individualTaqueroMethod(taqueroAdobada)
    

    # THREADS TAQUEROS INDIVIDUALES
    adobadaThread = Thread(target=individualTaqueroMethod, args=(taqueroAdobada,))
    tripaCabezaThread = Thread(target=individualTaqueroMethod, args=(taqueroTripaCabeza,))
    
    # THREADS TAQUEROS SHARED
    uno = Thread(target=sharedTaqueroMethod, args=(taqueroAsadaSuadero, taqueroAsadaSuadero.taquero1))
    dos = Thread(target=sharedTaqueroMethod, args=(taqueroAsadaSuadero, taqueroAsadaSuadero.taquero2))

    # THREAD STARTS
    uno.start()
    dos.start()
    adobadaThread.start()
    tripaCabezaThread.start()
    #printJson.start()
    chalanArribaThread.start()
    chalanAbajoThread.start()
    quesas.start()
    sqs_listener1.start()
    sqs_listener2.start()
    sqs_listener3.start()
    #visual.start()

    # THREAD JOINS
    chalanArribaThread.join()
    chalanAbajoThread.join()
    #printJson.join()
    quesas.join()
    uno.join()
    dos.join()
    adobadaThread.join()
    tripaCabezaThread.join()
    sqs_listener1.join()
    sqs_listener2.join()
    sqs_listener3.join()
    #visual.join()
    #np.save("test.npy", taqueroAsadaSuadero.__dict__)
    
    #sharedTaqueroMethod(taqueroAsadaSuadero)

