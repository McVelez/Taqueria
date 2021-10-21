from threading import Thread
import json
import queue
from time import sleep
import copy
import math


OrdersInProcessDictionary= {}
STATES = ["REJECTED","READY","RUNNING","EXIT"]
MEATS = ["asada", "adobada", "cabeza", "tripa", "suadero"]
TYPES = ["taco", "quesadilla"]
INGREDIENTS = ["salsa", "cilantro", "cebolla", "guacamole"]
CHALAN_WAITING_TIME = {"salsa":15, "cilantro":10, "cebolla":10, "guacamole":20, "tortillas":5}
TAQUERO_WAITING_TIME = {"salsa":0.5, "cilantro":0.5, "cebolla":0.5, "guacamole":0.5, "tortillas":0}
QUESADILLERO_STACK = 0

queueAdobada = queue.Queue()
queueAsadaSuadero = queue.Queue()
queueTripaCabeza = queue.Queue()
queueQuesadillas = queue.Queue()

class taqueroIndividual:
    def __init__(self, restTime, tacosNeededForRest, fan = False, tortillas = 50, stackQuesadillas = 5):
        self.fillings = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200}
        self.stackQuesadillas = stackQuesadillas
        self.fan = fan
        self.tortillas = tortillas
        self.restTime = restTime
        self.tacoCounter = 0
        self.tacosNeededForRest = tacosNeededForRest

    def activateFan(self):
        self.fan = True
        
    def deactivateFan(self):
        self.fan = False

    def rest(self):
        if(self.tacoCounter == 300):
            sleep(self.restTime)

class queues:
    def __init__(self):
        self.QOP = queue.Queue()
        self.QOGE = queue.Queue()
        self.QOGH = queue.Queue()
        self.QOQ = queue.Queue()

class taquerosShared:
    def __init__(self, restTime1, restTime2):
        self.taquero1 = taqueroIndividual(restTime1, 311)
        self.taquero2 = taqueroIndividual(restTime2, 313)
        queues.__init__(self)


class taco:
    def __init__(self, quantity, tacoDuration) -> None:
        self.quantity = quantity
        self.tacoDuration = tacoDuration

def checkIfEmpty(suborderList):
    return len(suborderList)==0

def assignToTaqueroQueue(suborder, key):
    # Si carne de tacos de la suborder es tripa o cabeza
    if(suborder['meat'] == MEATS[3] or suborder['meat'] == MEATS[2]):
        #AGREGAR suborder al queue del taquero de tripa y cabeza
        queueTripaCabeza.put(suborder)
        globalAssignator(queueTripaCabeza, taqueroTripaCabeza)
    # Si carne de tacos de la suborder es asada o suadero    
    if(suborder['meat'] == MEATS[0] or suborder['meat'] == MEATS[4]):
        #AGREGAR suborder al queue de los taqueros de asada
        queueAsadaSuadero.put(suborder)
        globalAssignator(queueAsadaSuadero, taqueroAsadaSuadero)
    # Si carne de tacos de la suborder es adobada    
    if(suborder['meat'] == MEATS[1]):
        #AGREGAR suborder al queue de Adobada
        queueAdobada.put(suborder)
        globalAssignator(queueAdobada, taqueroAdobada)
    index = suborder['part_id'].find('-')
    OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[1]

def maxSumOrder(orden, maxQuantity, key, type):
    isTaco = lambda x: x['type'] == TYPES[type]
    #print(orden,sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ), type)
    if sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ) > maxQuantity:
        OrdersInProcessDictionary[key]['status'] = STATES[0]
        for suborder in orden:
            suborder['status'] = STATES[0]
        return True
    return False

def categorizador(orden,key): # objeto de toda la orden

    minQuantityPerSuborder = 1
    maxQuantityPerSuborderTacos = 100
    maxQuantityPerSuborderQuesadillas = 50
    maxQuantityPerOrderTacos = 400
    maxQuantityPerOrderQuesadillas = 100

    # ESTADOS: REJECTED (0)| READY (1) | RUNNING (2)| EXIT (3)
    # Check if order is empty
    if checkIfEmpty(orden): OrdersInProcessDictionary[key]['status'] = STATES[0]
    # suborderes: no empty, 100 > tacos en suborder, 400 > tacos en total de orden
    flag = maxSumOrder(orden, maxQuantityPerOrderQuesadillas, key, 1)
    flag = maxSumOrder(orden, maxQuantityPerOrderTacos, key, 0)
    if flag:
        return

    for suborder in orden:
        # Check if type is supported
        index = suborder['part_id'].find('-')
        if suborder['type'] not in TYPES: 
            
            OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[0]
            continue
        
        if suborder['type'] == TYPES[0]:#taco
            # Check min and max of suborder
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderTacos: 
                OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[0]
                continue
        else:
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderQuesadillas: 
                OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[0]
                continue
        # Check if meat is supported
        if suborder['meat'] not in MEATS: 
            OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[0]
            continue
        
        # Check if ingredients are supported
        for ingredient in suborder['ingredients']:
            if ingredient not in INGREDIENTS: OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['status'] = STATES[0]

        #print(suborder['part_id'], suborder['type'], suborder['meat'], suborder['quantity'])
        if(suborder['status'] != STATES[0]):
            OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['remaining_tacos'] = OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['quantity']
            assignToTaqueroQueue(suborder, key)
    
def globalAssignator(queueNeeded, taqueroInstance):
    # dequeue del queue global
    suborder = queueNeeded.get()
    # enqueue al queue correpondiente del taquero
    # quantity, type
    # QUESADILLA
    if(suborder['type'] == TYPES[1]):
        # ENQUEUE AL QOQ del taquero de tripa y cabeza
        taqueroInstance.QOQ.put(suborder)
        #print("QOQ",taqueroInstance.__dict__['QOQ'].get())
    # TACOS
    if(suborder['quantity'] <= 25):
        taqueroInstance.QOP.put(suborder)
        #print("QOP",taqueroInstance.__dict__['QOP'].get())
    else:
        if(taqueroInstance.QOGE.empty()):
            if(taqueroInstance.QOGH.qsize() == 4):
                taqueroInstance.QOGE.put(suborder) 
                #print("QOGE",taqueroInstance.__dict__['QOGE'].get())   
            else:
                taqueroInstance.QOGH.put(suborder)
                #print("QOGH",taqueroInstance.__dict__['QOGH'].get())
        else:
            taqueroInstance.QOGE.put(suborder)    
            #print("QOGE",taqueroInstance.__dict__['QOGE'].get())
    

cantSubordersInQOGH = 4   

def individualTaqueroMethod(taquero):
    while(True):
        '''QOQ_copy = copy.copy(taquero.QOQ)
        subordenQ = []
        while (not QOQ_copy.empty()):
            subordenQ.append(QOQ_copy.get())
            taquero.QOQ.get()
        # acquire( Taquero.QOP )
        QOP_copy = copy.copy(taquero.QOP)
        subordenP = []
        while (not QOP_copy.empty()):
            subordenP.append(QOP_copy.get())
            taquero.QOP.get()
        # release bla'''
        
        
        for i in range(cantSubordersInQOGH):
            if taquero.QOGH.empty() is False:
                subordenG = taquero.QOGH.get()
                for tacos in range(math.floor(subordenG['quantity'] / 4)): # Note to self: revisa esto luego, ya que se debe identificar que el utlimo cuarto si sea completado en su totalidad
                    rest = cookFood(taquero, subordenG)
                    if rest:
                        taquero.rest()

                # if revisar si el counter de los tacos realizados para la subordenG es igual igual 0
                #       si si agregar en el diccionario que dicha suborden se encuentra en EXIT
                #       despues no reingresarlo al QOGH ni a nada pq ya quedó terminada     
                #       revisar si QOGE tiene subordenes en espera:
                #               si si entonces hacer taquero.QOGH.put(taquero.QOGE.get())       
                # si no entonces:
                #       hacer taquero.QOGH.put(subordenG) para colocar la suborden de vuelta al QOGH
        break
        # taquero.rest()
    

def cookFood(taquero, suborder):
    for ing in suborder['ingredients']:
        sleep(TAQUERO_WAITING_TIME[ing]) 
    taquero.tacoCounter += 1
    # hacer menos menos a la suborden de dicccionario en la variable de tacosRestantes
    index = suborder['part_id'].find('-')
    key = int(suborder['part_id'][:index])
    OrdersInProcessDictionary[key]['orden'][ int(suborder['part_id'][-(index):]) ]['remaining_tacos'] -=1

def sharedTaqueroMethod(Taquero, suborder):
    pass


def chalan():
    
    
    pass
    
joinear = []

def readJson(data):

    for orden in data:
        ordenObject = orden['orden'] # es una lista
        OrdersInProcessDictionary[orden['request_id']] = orden
        
        
        orden_thread = Thread(target=categorizador, args=(ordenObject, orden['request_id']))
        #i+=1  
        joinear.append(orden_thread)
        
        orden_thread.start()
        #categorizador(ordenObject, orden['request_id'])
        '''
        OrdersInProcessDictionary[orden['request_id']] = orden
        categorizador(ordenObject, orden['request_id'], i)

        '''

def nextOrder(qOrders):
    return qOrders.get()
#
def cliente(SQS1, SQS2, SQS3):
    pass

instanceQueues = queues()
taqueroAdobada = taqueroIndividual(3, 100)
taqueroTripaCabeza = taqueroIndividual(3, 100)
taqueroAsadaSuadero = taquerosShared(9.33, 9.39)
taqueroAdobada.__dict__.update(instanceQueues.__dict__)
taqueroTripaCabeza.__dict__.update(instanceQueues.__dict__)



if __name__ == "__main__":
    with open('ordersTest.json', 'r') as f:
    #with open('Ordenes.json', 'r') as f:
        data = json.load(f)
        f.close()
    
    readJson(data)
    print('kk')
    individualTaqueroMethod(taqueroAdobada)   
    #suborderAsignator(None)

    '''for thr in joinear:
        thr.join()'''
