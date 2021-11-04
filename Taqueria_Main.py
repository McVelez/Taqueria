from threading import Thread
import json
#import queue
from time import sleep
import copy
import math
import numpy as np
from collections import deque


OrdersInProcessDictionary= {}
STATES = ["REJECTED","READY","RUNNING","EXIT"] 
MEATS = ["asada", "adobada", "cabeza", "tripa", "suadero"]
TYPES = ["taco", "quesadilla"]
INGREDIENTS = ["salsa", "cilantro", "cebolla", "guacamole"]
CHALAN_WAITING_TIME = {"salsa":15, "cilantro":10, "cebolla":10, "guacamole":20, "tortillas":5}
INGREDIENTS_AT_MAX = {"tortillas":50, "salsa":150, "guacamole":100, "cilantro":200, "cebolla":200}
TAQUERO_WAITING_TIME = {"salsa":0.5, "cilantro":0.5, "cebolla":0.5, "guacamole":0.5, "tortillas":0}
QUESADILLERO_STACK = 0

queueAdobada = deque()
queueAsadaSuadero = deque()
queueTripaCabeza = deque()
queueQuesadillas = deque()

class taqueroIndividual:
    def __init__(self, restTime, tacosNeededForRest, id, fan = False, tortillas = 50, stackQuesadillas = 5):
        self.fillings = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200}
        self.stackQuesadillas = stackQuesadillas
        self.fan = fan
        self.id = id
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

def checkIfEmpty(suborderList):
    return len(suborderList)==0

def assignToTaqueroQueue(suborder, key):

    indexAd = MEATS.index('adobada')
    indexAs = MEATS.index('asada')
    indexTr = MEATS.index('tripa')
    indexCa = MEATS.index('cabeza')
    indexSu = MEATS.index('suadero')

    # Si carne de tacos de la suborder es tripa o cabeza
    if(suborder['meat'] == MEATS[indexTr] or suborder['meat'] == MEATS[indexCa]):
        #AGREGAR suborder al queue del taquero de tripa y cabeza
        queueTripaCabeza.append(suborder)
        globalAssignator(queueTripaCabeza, taqueroTripaCabeza)
    # Si carne de tacos de la suborder es asada o suadero    
    if(suborder['meat'] == MEATS[indexAs] or suborder['meat'] == MEATS[indexSu]):
        #AGREGAR suborder al queue de los taqueros de asada
        queueAsadaSuadero.append(suborder)
        globalAssignator(queueAsadaSuadero, taqueroAsadaSuadero)
    # Si carne de tacos de la suborder es adobada    
    if(suborder['meat'] == MEATS[indexAd]):
        #AGREGAR suborder al queue de Adobada
        queueAdobada.append(suborder)
        globalAssignator(queueAdobada, taqueroAdobada)
    index = suborder['part_id'].find('-')
    OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):]) )]['status'] = STATES[1]

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
            
            OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['status'] = STATES[0]
            continue
        
        if suborder['type'] == TYPES[0]:#taco
            # Check min and max of suborder
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderTacos: 
                OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['status'] = STATES[0]
                continue
        else:
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderQuesadillas: 
                OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['status'] = STATES[0]
                continue
        # Check if meat is supported
        if suborder['meat'] not in MEATS: 
            OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['status'] = STATES[0]
            continue
        
        # Check if ingredients are supported
        for ingredient in suborder['ingredients']:
            if ingredient not in INGREDIENTS: OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['status'] = STATES[0]

        #print(suborder['part_id'], suborder['type'], suborder['meat'], suborder['quantity'])
        if(suborder['status'] != STATES[0]):
            OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['remaining_tacos'] = OrdersInProcessDictionary[key]['orden'][ abs(int(suborder['part_id'][-(index):])) ]['quantity']
            assignToTaqueroQueue(suborder, key)
    
def globalAssignator(queueNeeded, taqueroInstance):
    # dequeue del queue global
    suborder = queueNeeded.pop()
    # enqueue al queue correpondiente del taquero
    # quantity, type
    # TACOS Y QUESADILLAS
    if(suborder['quantity'] <= 25):
        taqueroInstance.QOP.append(suborder)
        #print("QOP",taqueroInstance.__dict__['QOP'].pop())
    else:
        if(taqueroInstance.QOGE):
            if(len(taqueroInstance.QOGH) == 4):
                taqueroInstance.QOGE.append(suborder) 
                #print("QOGE",taqueroInstance.__dict__['QOGE'].pop())   
            else:
                taqueroInstance.QOGH.append(suborder)
                #print("QOGH",taqueroInstance.__dict__['QOGH'].pop())
        else:
            taqueroInstance.QOGE.append(suborder)    
            #print("QOGE",taqueroInstance.__dict__['QOGE'].pop())
    
cantSubordersInQOGH = 4   

def quesadillero():
    while True:
        # NOTA: Va a funcionar como un FIFO?
        # AGREGAR STACK
        if (queueQuesadillas):
            suborden = queueQuesadillas.pop()
            # notificar que sta haciendo quesadilla 'tal'
            #sleep( 20 * suborden[0]['quantity'])
            # indice para identificar a la suborden dentro del diccionario
            print(suborden['part_id'])
            index = suborden['part_id'].find('-')
            # llave de la orden a la que pertenece
            key = int(suborden[0]['part_id'][:index])
            # poner estado de suborden como exit
            OrdersInProcessDictionary[key]['orden'][abs(int(suborden[0]['part_id'][-(index):]))]['status'] = STATES[3]
            if (suborden[2]):
                dispatcher(suborden)

def dispatcher(suborden): # suborden es una tupla (sub , taquero.id, 0)
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
    # out of service 
    pass

def individualTaqueroMethod(taquero):
    while(True):
        # NOTA 2.0 Cuando llegue una suborden de quesadillas, se le tratará como taco (poniendole ingredientes y carne)
        #   y se enviará al quesadillero para que el ponga su quesito y no tenga que regresarlo al tqeuro de nuevo.
        # Copiamos el queue a otro espacio de memoria
        QOP_copy = copy.deepcopy(taquero.QOP)
        snapshotQOP = []
        # se genera el snapshot al vaciar tnto la copia como el queue original
        # no olvidar agregar llamada a quesadillero para cuando no haya suficientes
        while (len(QOP_copy)>0):
            subor = QOP_copy.pop() 
            snapshotQOP.append(subor)
            taquero.QOP.pop()
        # se iteran las subordenes del snapshot
        snapshotQOP = snapshotQOP[::-1]
        for sub in snapshotQOP:
            # indice para identificar a la suborden dentro del diccionario
            index = sub['part_id'].find('-')
            # llave de la orden a la que pertenece
            key = int(sub['part_id'][:index])
            stackTaken = False
            if (sub['type']==TYPES[1]):
                if (sub['quantity'] <= taquero.stackQuesadillas):
                    # darle las quesadillas
                    taquero.stackQuesadillas -= sub['quantity']
                    #taquero.stackQuesadillas += sub['quantity'] # temporal!!!!!!!!!!!!!!!!!
                    peticionQuesadillas = (sub , taquero.id, 1)
                    queueQuesadillas.append(peticionQuesadillas)  #quesadillas dispatcher que el va usar IDS y todo eso 
                    stackTaken = True
            # llamar a pedir las quesadillas que se van a utilizar
            # se itera por cada taco en la suborden de quesadillas
            for taco in range(sub['quantity']):
                # se hace cada taco
                cookFood(taquero, sub, key, index)
            
            if sub['type']==TYPES[1] and stackTaken == False:
                peticionQuesadillas = (sub , taquero.id, 0)
                queueQuesadillas.append(peticionQuesadillas)

            print(sub['part_id'], "done")
        # acquire( Taquero.QOP )
        # release bla 
        
        
        for i in range(cantSubordersInQOGH):
            if taquero.QOGH is False:
                # Logica de preparacion de cada taco de cada suborden grande dentro del QOGH
                subordenG = taquero.QOGH.pop()
                index = subordenG['part_id'].find('-')
                key = int(subordenG['part_id'][:index])
                
                cantTacosPorHacer = math.floor(subordenG['quantity'] / 4)
                # En base al siguiente condicional aseguramos que cada suborden siempre sea completada en exactamente 4 repeticiones
                if(OrdersInProcessDictionary[key]['orden'][abs(int(subordenG['part_id'][-(index):]))]['remaining_tacos'] / cantTacosPorHacer < 2):
                    cantTacosPorHacer = OrdersInProcessDictionary[key]['orden'][abs(int(subordenG['part_id'][-(index):]))]['remaining_tacos']

                # Por aqui va lo de agregar RUNNING al diccionario de los estados
      
                for tacos in range(cantTacosPorHacer): 
                    rest = cookFood(taquero, subordenG, key, index )
                    if rest:
                        taquero.rest()
                # Logica de actualizacion de diccionario y revision de subordenes grandes completadas
                if (OrdersInProcessDictionary[key]['orden'][abs(int(subordenG['part_id'][-(index):]))]['remaining_tacos'] == 0):
                    if subordenG['type'] == TYPES[TYPES.index('quesadilla')]:
                        subordenQues = (subordenG, taquero.id, 0)
                        queueQuesadillas.append(subordenQues)
                    else:
                        OrdersInProcessDictionary[key]['orden'][abs(int(subordenG['part_id'][-(index):]))]['status'] = STATES[3]
                    if (taquero.QOGE is False):
                        taquero.QOGH.append(taquero.QOGE.pop())
                else:
                    taquero.QOGH.append(subordenG)
        break

def cookFood(taquero, suborder, key, index):
    sleep(1)
    
    while(taquero.tortillas == 0):
        pass
    
    for ing in suborder['ingredients']:
        while (taquero.fillings[ing] == 0):
            pass
        
        sleep(TAQUERO_WAITING_TIME[ing])
        taquero.fillings[ing] -= 1
        

    taquero.tacoCounter += 1
    print(suborder['part_id'])
    # hacer menos menos a la suborden de dicccionario en la variable de tacosRestantes
    OrdersInProcessDictionary[key]['orden'][abs( int(suborder['part_id'][-(index):]))]['remaining_tacos'] -=1

def sharedTaqueroMethod(Taquero):
    taque1 = Taquero.taquero1
    taque2 = Taquero.taquero2
    # QOP 
    # taquero.FLAG si un taquero esta haciendo ordenes pequenias
        # SI HAY ALGUIEN
            # ESE TAQUERO SE ENCARGA DE CONTINUAR SACANDO COSAS DEL QOP Y HACIENDOLAS
            # SI EL QOP ESTA VACIO SE CAMBIA SU FLAG PARA HACER ORDENES DEL QOGH

        # NO HAY NADIE
            # SE ESPERA LA ORDEN A QUE ALGUNO DE LOS DOS TAQUEROS TERMINE DE HACER SU OCTAVO Y A DICHO
            #    TAQUERO SE LE ASIGNA EL FLAG DE HACER LAS ORDENES PEQUENIAS
    
    pass

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
        ingredientsA = [(taqueroAdobada.fillings[a],i) for a,i in zip(list(taqueroAdobada.__dict__['fillings']), range(1,5))]
        ingredientsS= [(taqueroAsadaSuadero.taquero1.fillings[a],i) for a,i in zip(list(taqueroAsadaSuadero.taquero1.__dict__['fillings']), range(4))]
        fillingsList = [[(taqueroAdobada.tortillas,0)],[(taqueroAsadaSuadero.taquero1.tortillas,0)]]
        fillingsList[0].extend(ingredientsA)
        fillingsList[1].extend(ingredientsS)
        fillingsList[0] = [ (porcentaje(a[0], fillingsList[0].index(a)), a[1]) for a in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(a[0], fillingsList[1].index(a)), a[1]) for a in fillingsList[1] ]
        if min(fillingsList[0]) >= min(fillingsList[1]):
            do = min(fillingsList[1])
            if do == 1:
                continue
            which = list(taqueroAsadaSuadero.taquero1.__dict__['fillings'])[do[1]]
            taqueroAsadaSuadero.taquero1.fillings[which] = INGREDIENTS_AT_MAX[which]
            # PREGUNTAR SI TENEMOS QUE NOTIFICAR
            sleep(CHALAN_WAITING_TIME[which])
        else:
            do = min(fillingsList[0])
            if do == 1:
                continue
            which = list(taqueroAdobada.__dict__['fillings'])[do[1]]
            taqueroAdobada.fillings[which] = INGREDIENTS_AT_MAX[which]
            sleep(CHALAN_WAITING_TIME[which])
            
def chalanAbajo():
    
    while True:
        ingredientsT = [(taqueroTripaCabeza.fillings[a],i) for a,i in zip(list(taqueroTripaCabeza.__dict__['fillings']), range(1,5))]
        ingredientsS= [(taqueroAsadaSuadero.taquero2.fillings[a],i) for a,i in zip(list(taqueroAsadaSuadero.taquero2.__dict__['fillings']), range(4))]
        fillingsList = [[(taqueroTripaCabeza.tortillas,0)],[(taqueroAsadaSuadero.taquero2.tortillas,0)]]
        fillingsList[0].extend(ingredientsT)
        fillingsList[1].extend(ingredientsS)
        fillingsList[0] = [ (porcentaje(a[0], fillingsList[0].index(a)), a[1]) for a in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(a[0], fillingsList[1].index(a)), a[1]) for a in fillingsList[1] ]
        if min(fillingsList[0]) >= min(fillingsList[1]):
            do = min(fillingsList[1])
            if do == 1:
                continue
            which = list(taqueroAsadaSuadero.taquero2.__dict__['fillings'])[do[1]]
            taqueroAsadaSuadero.taquero2.fillings[which] = INGREDIENTS_AT_MAX[which]
            # PREGUNTAR SI TENEMOS QUE NOTIFICAR
            sleep(CHALAN_WAITING_TIME[which])
        else:
            do = min(fillingsList[0])
            if do == 1:
                continue
            which = list(taqueroTripaCabeza.__dict__['fillings'])[do[1]]
            taqueroTripaCabeza.fillings[which] = INGREDIENTS_AT_MAX[which]
            sleep(CHALAN_WAITING_TIME[which])
        

joinear = []

def readJson(data):

    for orden in data:
        ordenObject = orden['orden'] # es una lista
        OrdersInProcessDictionary[orden['request_id']] = orden
        
        #orden_thread = Thread(tarpop=categorizador, args=(ordenObject, orden['request_id']))
        #i+=1  
        #joinear.append(orden_thread)
        
        #orden_thread.start()
        categorizador(ordenObject, orden['request_id'])
        
        '''
        OrdersInProcessDictionary[orden['request_id']] = orden
        categorizador(ordenObject, orden['request_id'], i)

        '''

def nextOrder(qOrders):
    return qOrders.pop()
#
def cliente(SQS1, SQS2, SQS3):
    pass

# adobada =0, taquero1 =1, taquero2=2, tripa 3
instanceQueues = queues()
taqueroAdobada = taqueroIndividual(3, 100, 0)
taqueroTripaCabeza = taqueroIndividual(3, 100, 3)
taqueroAsadaSuadero = taquerosShared(9.33, 9.39, 1, 2)
taqueroAdobada.__dict__.update(instanceQueues.__dict__)
taqueroTripaCabeza.__dict__.update(instanceQueues.__dict__)

def porcentaje(a,b):
    return a / INGREDIENTS_AT_MAX[list(INGREDIENTS_AT_MAX.keys())[b]]


if __name__ == "__main__":
    with open('ordersTest.json', 'r') as f:
    #with open('Ordenes.json', 'r') as f:
        data = json.load(f)
        f.close()
    
    readJson(data)
    #np.save("test.npy", taqueroAsadaSuadero.__dict__)

    #sharedTaqueroMethod(taqueroAsadaSuadero)
    individualTaqueroMethod(taqueroAdobada)   
    #suborderAsignator(None)

    '''for thr in joinear:
        thr.join()'''
