from threading import Thread
import threading
import json
import boto3
from time import sleep
import math
from collections import deque
from datetime import datetime
from dateutil import parser
# Las siguientes 3 librerias llaman las funciones que permiten realizar la comunicación con el SQS
from AWS.RoundRobin import SQS_handler
# Establece comunicación con el mlo encargado de comunicarse con el visualizador (node js)
from visualizador.communicate import sendToNode

# Se crea el cliente de SQS y se escribe el link del SQS del cual la taquería va leer
sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/292274580527/sqs_cc106_team_7"

# Diccionario para mantener un orden y gestión de todas las acciones que realizan los taqueros 
# sobre las subórdenes (Estados, la metadata de subordenes e información de acciones de involucrados con dicha suborden)
OrdersInProcessDictionary= {}

# Listado de posibles estados en los que puede estar una orden y/o suborden
STATES = ["REJECTED","READY","RUNNING","EXIT"] 

# Listado de carnes que utiliza la taquería para realizar tacos
MEATS = ["asada", "adobada", "cabeza", "tripa", "suadero"]

# Listado de los posibles tipos de peticion de alimento de una suborden
TYPES = ["taco", "quesadilla"]

# Listado de ingredientes utilizados por la taquería 
INGREDIENTS = ["salsa", "cilantro", "cebolla", "guacamole"]

# Diccionario que contiene el tiempo que le toma al chalan llenar un filling respectivamente
CHALAN_WAITING_TIME = {"salsa":15, "cilantro":10, "cebolla":10, "guacamole":20, "tortillas":5}

# Diccionario con la cantidad máxima que se puede llenar su respectivo filling
INGREDIENTS_AT_MAX = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200, "tortillas":50}

# Diccionario que contiene el tiempo que le toma al taquero agregar dicho filling a un taco/quesadilla
TAQUERO_WAITING_TIME = {"salsa":0.5, "cilantro":0.5, "cebolla":0.5, "guacamole":0.5, "tortillas":0}

# Inicializamos los queues de la taquería
queueAdobada = deque()
queueAsadaSuadero = deque()
queueTripaCabeza = deque()
queueQuesadillas = deque()

# Cantidad de subordnes posibles en un QOGH
cantSubordersInQOGH = 4   

# Clase para un taquero individual (las tauqeros como tal involucrados en la taquería)
class taqueroIndividual:
    # Instancia inicial de las variables de cada taquero, considerando las posibles diferencias entre cada uno: 
    # los tiempos de descanso, sus ventiladores, identificadores, cantidad de tacos para descansar y sus stack de quesadillas
    def __init__(self, restTime, tacosNeededForRest, id, fan = False, stackQuesadillas = 5):
        self.fillings = {"salsa":150, "guacamole":100, "cebolla":200, "cilantro":200, "tortillas":50}
        self.stackQuesadillas = stackQuesadillas
        self.fan = fan
        self.id = id
        self.flag = False
        self.restTime = restTime
        self.tacoCounter = 0
        self.tacosNeededForRest = tacosNeededForRest

    # Metodo que verifica si el taquero debe descansar    
    def rest(self):
        # Verifica si el residuo de los tacos hechos sobre los tacos requeridos para descanzar es cero
        if(self.tacoCounter != 0 and self.tacoCounter % self.tacosNeededForRest == 0):
            sleep(self.restTime)
            return True
        return False

# Define los queues requeridos para cada tipo de taquero (individual o compartido)
class queues:
    def __init__(self):
        self.QOP = deque()
        self.QOGE = deque()
        self.QOGH = deque()

# Se definen los dos taqueros que comparten el mismo queue con sus respectivas variables y se le relacionan sus queues con los que trabajan
class taquerosShared:
    def __init__(self, restTime1, restTime2, id1, id2):
        self.taquero1 = taqueroIndividual(restTime1, 311, id1)
        self.taquero2 = taqueroIndividual(restTime2, 313, id2)
        queues.__init__(self)


# Método que revisa si el taquero que recibió como parámetro ha realizado una cantidad de tacos del modulo de 600,
# en caso de que sí, se prende su ventilador y después de 60 seg se apaga.
def fan_(taquero):
    while(True):
        # Verifica si el residuo sobre 600 es cero y el taquero lleva por lo menos un taco
        if (taquero.tacoCounter != 0 and taquero.tacoCounter % 600 == 0):
            taquero.fan = True
            print("EL VENTILADOR DEL {0} SE HA PRENDIDO".format(taquero.id))
            sleep(60)
            taquero.fan = False

# Función para asignar suborden a su taquero correspondiente
def assignToTaqueroQueue(suborder, key):
    orden = OrdersInProcessDictionary[key]
    who = "Categorizador"
    
    # Se obtienen los indices correspondientes a los tipos de carne aceptados por la taquería 
    # (de este modo se pueden agregar tipos de carne sin tener que modificar muchos elementos del código)
    indexAd = MEATS.index('adobada')
    indexAs = MEATS.index('asada')
    indexTr = MEATS.index('tripa')
    indexCa = MEATS.index('cabeza')
    indexSu = MEATS.index('suadero')

    # Si carne de tacos de la suborder es tripa o cabeza
    if(suborder['meat'] == MEATS[indexTr] or suborder['meat'] == MEATS[indexCa]):
        # Se agrega suborden al queue del taquero de tripa y cabeza
        queueTripaCabeza.append(suborder)
        
        # Se le regresa al response el log de la suborden que se agregó al queue de tripa y cabeza
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Tripa y Cabeza".format(suborder['part_id']))
        globalAssignator(queueTripaCabeza, taqueroTripaCabeza)
    
    # Si carne de tacos de la suborder es asada o suadero    
    if(suborder['meat'] == MEATS[indexAs] or suborder['meat'] == MEATS[indexSu]):
        # Se agrega suborden al queue de los taqueros de asada
        queueAsadaSuadero.append(suborder)
        
        # Se le regresa al response el log de la suborden que se agregó al queue de asada y suadero
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Asada y suadero".format(suborder['part_id']))
        globalAssignator(queueAsadaSuadero, taqueroAsadaSuadero)
    
    # Si carne de tacos de la suborder es adobada    
    if(suborder['meat'] == MEATS[indexAd]):
        # Se agrega suborden al queue de Adobada
        queueAdobada.append(suborder)
        
        # Se le regresa al response el log de la suborden que se agregó al queue de adobada
        responseOrden(key, orden, who, "La suborden {0} se agregó al queue de Adobada".format(suborder['part_id']))
        globalAssignator(queueAdobada, taqueroAdobada)

# Se crea el lock para evitar concurrencias en el cálculo de sumas
lockMaxSum = threading.Lock()

# Se define la fucnión para calcular la suma de tacos y/o quesadillas de la orden
# recibiendo la orden, la cnatidad permitida, la llave dentro del diccionario y el tipo (tacos o quesadillas))
def maxSumOrder(orden, maxQuantity, key, type):
    # Se adquiere el lock 
    lockMaxSum.acquire()
    
    # Se obtiene la orden del diccionario
    ordenCompleta = OrdersInProcessDictionary[key]
    
    # Se define una 'función' que verifique si el tipode determinada suborden es el requeridoo por la llamada a la función
    isTaco = lambda x: x['type'] == TYPES[type]
    
    # Se obtiene la suma de tacos y/o quesadillas para identificar que no supere el maximo de quesadillas o tacos de toda la orden
    if sum( [ x['quantity'] if isTaco(x) else 0 for x in orden] ) > maxQuantity:
        # Si sí superan entonces se rechaza toda la orden
        OrdersInProcessDictionary[key]['status'] = STATES[0]
        
        # Se le regresa al response el log del rechazo de la orden que sobrepasó la cantidad total del límite aceptado
        responseOrden(key, ordenCompleta, "Categorizador", "Rechazó orden (Cantidad total excede el limite aceptado)")
        
        # Todas las subordenes que acompañan a dicha orden rechazada también son establecidas como REJECTED
        for suborder in orden:
            suborder['status'] = STATES[0]
        lockMaxSum.release()

        # Se regresa True si se supero el limite establecido
        return True
    lockMaxSum.release()
    
    # Si las cantidades de dicha orden entran dentro de los limites establecidos se regresa False
    return False

# Se define la función para calcular los milisegundos de diferencia entre dos fechas dadas
def calcularMS(DateLlegada, DateAccion):
    # Se parsean las fechas para realizar una resta y conversión a milisegundos
    date1 = parser.parse(str(DateAccion))
    date2 = parser.parse(DateLlegada)
    ms = int((date1 - date2).total_seconds() * 1000)

    # Se regresa el total de milisegundos
    return ms

# Se define la función para construir y añadir la respuesta de cada acción realizada respecto a cada orden
def responseOrden(key, orden, who, what):
    # Se añade a la respuesta los parámetros recibidos en forma de diccionario
    # calculando el tiempo actual de respuesta
    OrdersInProcessDictionary[key]['response'].append({
        "Who" : who,
        "When" : str(datetime.now()) ,
        "What" : what,
        "Time" : calcularMS(orden['datetime'], datetime.now())
        })

# Se instancia el lock encargado de verificar que no existan accesos que cambien la asignación
# de una orden por context switch
lockCategorizar = threading.Lock()

# Se define la función encaragda de realizar la categorización de las subordenes a su respectivo tipo de carne
# aceptar o recharzarlas, receibiendo la orden completa y su respectiva llave dentro del diccionario de ordenes
def categorizador(ordenCompleta,key):
    who = "Categorizador"

    # Se adquiere el lock
    lockCategorizar.acquire()
    
    # Se obtienen las subórdenes componentes de la orden completa
    orden = ordenCompleta['orden']
    
    # Se crean las siguientes variables que definen las limitaciones y consideraciones que se realizan para cada suborden y orden
    # de quesadillas y de tacos
    minQuantityPerSuborder = 1
    maxQuantityPerSuborderTacos = 100
    maxQuantityPerSuborderQuesadillas = 35
    maxQuantityPerOrderTacos = 400
    maxQuantityPerOrderQuesadillas = 70
    
    # Se inicializa la respuesta de la orden 
    OrdersInProcessDictionary[key]['response'] = []
    
    # Se verifica que la orden no se encuentre vacía
    if len(orden)==0: 
        OrdersInProcessDictionary[key]['status'] = STATES[0]
        
        # Se le regresa al response el log del rechazo de una orden vacía
        responseOrden(key, ordenCompleta, who, "Rechazó orden (orden vacía)")


    # Se verifica que la orden completa cumpla con los requisitos de tamaño de la taqueria para ser aceptada
    # En primera instancia para quesadillas seguido por tacos
    flag = maxSumOrder(orden, maxQuantityPerOrderQuesadillas, key, 1)
    flag = maxSumOrder(orden, maxQuantityPerOrderTacos, key, 0)
    
    # Si alguna de los dos (quesadillas o tacos) viola las restricciones, la orden completa no se acepta
    if flag:
        return
    
    # Se itera por las subordenes de la orden aceptada
    for suborder in orden:
        # NOTA: Si existe cualqueir violación a las restricciones se establece continue para validar la siguiente suborden en caso de existir

        # Se obtiene el índice de la subórden dentro de la lista de la órden padre
        index = len(suborder['part_id'].split('-')[1])
        suborderIndex = int(suborder['part_id'][-index:])
        
        # Si el tipo de la suborden no es disponible/utilizada por la taquería se descarta
        if suborder['type'] not in TYPES: 
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
            
            # Se le regresa al response el log del rechazo de una suborden con tipo inexistente
            responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No existe el tipo)".format(suborder['part_id']))
            continue
        
        # Si el tipo de la suborden es un taco
        if suborder['type'] == TYPES[0]:
            # Si el numero de tacos de la suborden supera alguno de los limites establecidos se descarta
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderTacos: 
                OrdersInProcessDictionary[key]['orden'][ suborderIndex ]['status'] = STATES[0]
                
                # Se le regresa al response el log del rechazo de una suborden con el límite de tacos excedido
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (Cantidad excede el limite de tacos)".format(suborder['part_id']))
                continue
        else:
            # Si el numero de quesadillas de la suborden supera alguno de los limites establecidos se descarta
            if suborder['quantity'] < minQuantityPerSuborder or suborder['quantity'] > maxQuantityPerSuborderQuesadillas: 
                OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
                
                # Se le regresa al response el log del rechazo de una suborden con el límite de quesadillas excedido
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (Cantidad excede el limite de quesadillas)".format(suborder['part_id']))
                continue
        
        # Si la carne no es disponible/utilizada por la taquería se descarta dicha suborden 
        if suborder['meat'] not in MEATS: 
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
            
            # Se le regresa al response el log del rechazo de una suborden con un tipo de carne no aceptada
            responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No acepta esa carne)".format(suborder['part_id']))
            continue
        
        # Si alguno de los ingredientes de la suborden no es disponible/utilizada por la taquería se descarta 
        for ingredient in suborder['ingredients']:
            if ingredient not in INGREDIENTS: 
                OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[0]
                
                # Se le regresa al response el log del rechazo de una suborden con un ingrediente no aceptado
                responseOrden(key, ordenCompleta, who, "Rechazó suborden {0} (No acepta el ingrediente)".format(suborder['part_id']))
                break

        # Si el estado de la suborden no es REJECTED se establece en el diccionario de ordenes en proceso la cantidad de tacos restantes,
        # y se establece el estado de la suborden como READY para posteriormente asignarlo a un queue
        if(suborder['status'] != STATES[0]):
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['remaining_tacos'] = OrdersInProcessDictionary[key]['orden'][suborderIndex]['quantity']
            OrdersInProcessDictionary[key]['orden'][suborderIndex]['status'] = STATES[1]
            
            # Se le regresa al response el log del cambio de estado de la suborden a READY
            responseOrden(key, ordenCompleta, who, "La suborden {0} entra en estado READY".format(suborder['part_id']))
            
            # Una vez filtrado en base a las condiciones se asigna dicha suborden a un queue
            assignToTaqueroQueue(suborder, key)

    # Se libera el lock
    lockCategorizar.release()


# Se crea un lock para asegurar que una suborden no entre a un queue cuando no deba 
lockAsign = threading.Lock()

# Se define la función que asigna las subórdenes a los queues respectivos de cada taquero (QOP, QOGH o QOGE)
def globalAssignator(queueNeeded, taqueroInstance):
    who = "Asignador Global"
    # Se hace pop de un queue Correspondiente (tripa y cabeza, asada y suadero o adobada)
    suborder = queueNeeded.pop()
    
    # Se obtiene la llave de dicha suborden
    key = int(suborder['part_id'].split('-')[0])

    # Se adquiere el lock para evitar asignaciones y pops concurrentes
    lockAsign.acquire()
    
    # Se establece una variable para determinar el quueue al que se está asignando (necesario para adjuntarlo como respuesta en nuestro diccionario de respuestas)
    where = None
    
    # Si la cantidad de tacos a realizar en la suborden es menor o igual a la permitida para 
    # considerarla una suborden pequeña 
    if(suborder['quantity'] <= 25):
        # Se verifica que no se esté haciendo un pop en alguna otro acceso al QOP
        while lockPop.locked()==True:
            pass
        
        # Se agrega al QOP la suborden
        taqueroInstance.QOP.append(suborder)
        where = 'QOP'
        
    else:
        # Si el QOGE está vacío
        if(len(taqueroInstance.QOGE) == 0):
            # Si el QOGH está justamente lleno
            if(len(taqueroInstance.QOGH) == 4):
                # Si no hay espacio en el QOGH entonces se agrega al QOGE
                while lockPop.locked() == True:
                    pass
                taqueroInstance.QOGE.append(suborder) 
                where = 'QOGE'   
            else:
                # Si hay espacio en el QOGH se agrega dicha suborden 
                while lockPop.locked() == True:
                    pass
                taqueroInstance.QOGH.append(suborder)
                where = "QOGH"
                
        else:
            # Si el QOGE no está vacío entonces tiene subordenes (QOGE y QOGH), por lo que dicha suborden también es agregada a dicho queue
            while lockPop.locked() == True:
                pass
            taqueroInstance.QOGE.append(suborder)  
            where = 'QOGE'  
            
    # Variable para obtener el nombre del taquero en el que agregó una suborden
    name = taqueroInstance.__class__.__name__
    
    # Se le regresa al response el log de la suborden que fue agregada al queue respectivo del taquero
    responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} agregada a {1} de taquero {2}".format(suborder['part_id'],where, name))
    lockAsign.release()

# Se define la función que implementa las funcionalidades del quesadillero
def quesadillero():
    # Se llama la variable global para recibir metadata
    global currentQuesadilla
    who = 'quesadillero'
    
    # Debido a que es un thread siempre está realizando esta función 
    while True:
        # Si hay subordenes en el Queue de quesadillas
        if (queueQuesadillas):
            # Se obtiene una suborden de quesadillas del Queue
            suborden = queueQuesadillas.pop()

            # Se obtiene la longitud de la suborden en formato de texto y se obtiene el indice como entero
            index = len(suborden[0]['part_id'].split('-')[1])
            index = int(suborden[0]['part_id'][-index:])
            
            # Llave de la orden a la que pertenece
            key = int(suborden[0]['part_id'].split('-')[0])

            # Si es un relleno del stack
            if (suborden[2]):
                # Se le regresa al response el log de que se comenzó a hacer quesadillas para el taquero
                responseOrden(key, OrdersInProcessDictionary[key], who, "Comienza a hacer {0} quesadillas para taquero {1}".format(suborden[0]['quantity'], suborden[1]))
            else:
                # Se le regresa al response el log de que se comenzó a hacer una suborden
                responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} comienza a hacerse".format(suborden[0]['part_id']))
            
            # Notificar que esta haciendo quesadilla 'tal'
            if (not suborden[2]):
                print("Quesadillero haciendo suborden de quesadillas {0}".format(suborden[0]['part_id']))
            
            # Por cada quesadilla en la petición
            for quesadillaCount in range(suborden[0]['quantity']):
                # Se genera la espera durante el tiempo requerido para cada quesadilla
                sleep(20)
                
                # Si es una quesadilla de una suborden y no de una petición de stack
                if (not suborden[2]):
                    # Se actualiza la metadata del visualizador para las quesadillas actuales
                    currentQuesadilla = [suborden[0]['part_id'], suborden[0]['quantity'] - quesadillaCount, len(queueQuesadillas)]
            currentQuesadilla = []
            
            # Si es un relleno del stack
            if (not suborden[2]):
                # Se elimina la subórden de la metadata de la suborden ya terminada
                print("Quesadillero ha terminado")
                info.pop(suborden[0]['part_id'])
            
            # Se actualiza el diccionario de respuesta en donde: si es una petición de rellenado de stack se menciona y se manda al dispatcher para darles las quesadillas en sus stacks
            # o se completa la suborden de quesadillas y se adjunta como completada en el diccionario de respuesta
            if (suborden[2]):
                # Se le regresa al response el log de que se terminó de hacer quesadillas para el taquero
                responseOrden(key, OrdersInProcessDictionary[key], who, "Termina a hacer {0} quesadillas para taquero {1}".format(suborden[0]['quantity'], suborden[1]))
                dispatcher(suborden, key)
            else: 
                # Se le regresa al response el log de que la suborden fue hecha
                OrdersInProcessDictionary[key]['orden'][index]['status'] = STATES[3]
                responseOrden(key, OrdersInProcessDictionary[key], who, "Suborden {0} hecha".format(suborden[0]['part_id']))
                
                # Se verifica que la orden padre ya esté completada
                mergeFinishedOrders(key)

# Se define la función del surtidor de quesadillas a los stacks de los taqueros                
def dispatcher(suborden, key): 
    # Suborden es una tupla (sub , taquero.id, 0) En donde Adobada-0, taquero1-1, taquero2-2, tripa-3   
    who = "Dispatcher"
    
    # De acuerdo al id de taquero, se le regresan quesadillas para su stack de quesadillas
    if suborden[1] == 0:
        taqueroAdobada.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 1:
        taqueroAsadaSuadero.taquero1.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 2:
        taqueroAsadaSuadero.taquero2.stackQuesadillas += suborden[0]['quantity']
    if suborden[1] == 3:
        taqueroTripaCabeza.stackQuesadillas += suborden[0]['quantity']
    
    # Una vez despachada la orden de quesadillas se actualiza el diccionario de respuesta mencionando la acción realizada
    print("despachando orden", suborden[0]['part_id'])
    responseOrden(key, OrdersInProcessDictionary[key], who, "{0} quesadillas agregadas a stack de taquero {1}".format(suborden[0]['quantity'], suborden[1]))

# Se crea un lock para asegurar que un taquero no intente hacer un pop de un queue vacío
lockPop = threading.Lock()

# Se crea un lock para mantener la integirad de las llaves e indices
lockGetKeys = threading.Lock()

def individualTaqueroMethod(taquero):
    # Se define la instancia del taquero actual
    who = "Taquero " + str(taquero.id)
    
    # Se genera una iteración "infinita" para los threads que atienden a esta función
    while(True): 
        # Verificamos que no se esté insertando en el queue
        while lockAsign.locked()==True:
            pass

        # Si el QOP del taquero tiene uno o más subordenes se hace pop para obtener una
        if (len(taquero.QOP)>0):
            lockPop.acquire()
            sub = taquero.QOP.pop()
            
            # Se obtiene la longitud de la suborden en formato de texto
            index = len(sub['part_id'].split('-')[1])
            
            # Se obtiene el entero representativo del número de suborden actual en relación a su orden padre
            subordenIndex = int(sub['part_id'][-index:])
            
            # Se obtiene la llave de la orden a la que pertenece
            key = int(sub['part_id'].split('-')[0])
            
            # Se obtene la orden completa a la que pertenece la suborden
            ordenCompleta = OrdersInProcessDictionary[key]
            
            # Se regresa al response el log de la suborden de QOP en proceso
            responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOP)".format(sub['part_id']))
            lockPop.release()
            
            # Variable para identificar is se tomó del stack
            stackTaken = False
            
            # Si la subórden es una quesadilla
            if (sub['type']==TYPES[1]):
                # Se verifica si es posible tomar las quesadillas disponibles en el stack del taquero
                if (sub['quantity'] <= taquero.stackQuesadillas):
                    # El taquero toma las quesadillas disponibles de su stack
                    taquero.stackQuesadillas -= sub['quantity']
                    peticionQuesadillas = (sub , taquero.id, 1)
                    
                    # Hace una petición de quesadillas para rellenar su stack
                    queueQuesadillas.append(peticionQuesadillas)
                    stackTaken = True

            # Se itera por cada taco en la suborden de quesadillas
            for taco in range(sub['quantity']):
                cookFood(taquero, sub, key, subordenIndex)
                info[sub['part_id']] = [sub["part_id"], sub["type"], sub["meat"], sub["remaining_tacos"]]
                
                # Se actualiza la información del visualizador
                sendMetadata()
                if taquero.rest():
                    # Si el taquero si descanso agregarlo como accion en nuestra Respuesta
                    responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(taquero.id))
                    
            
            # Se verifica quue la subórden actual sea de quesadillas y no se hayan tomado las quesadillas del stack
            if sub['type']==TYPES[1] and stackTaken == False:
                # Se gener una peticicón para finalizar las quesadillas de la subórden
                peticionQuesadillas = (sub , taquero.id, 0)

                # Se agrega la petición al queue del quesadillero
                queueQuesadillas.append(peticionQuesadillas)
                
                # Se le regresa al response el log de la suborden del QOP que fue enviada al quesadillero
                responseOrden(key, ordenCompleta, who, "Suborden {0} enviada a quesadillero (QOP)".format(sub['part_id']))
            else:
                # Si la orden es un taco se elimina de la metadata del visualizador
                info.pop(sub['part_id'])

                # Se le regresa al response el log de la suborden del QOP que fue completada
                responseOrden(key, ordenCompleta, who, "Suborden {0} es completada (QOP)".format(sub['part_id']))
                
                # Establecemos en el diccionario de ordenes en proceso el estado de la suborden como EXIT
                OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                # Se verifica que la orden padre ya esté completada
                mergeFinishedOrders(key)
            print("done") 
        
        # Por cada suborden dentro del QOGH
        for i in range(cantSubordersInQOGH):
            # Si el QOGH tiene alguna suborden por realizar
            if len(taquero.QOGH)>0:
                # Se obtiene la suborden grande del QOGH
                subordenG = taquero.QOGH.pop()

                # Se hace un acquire de un lock para asegurar que las llaves e indices utilizados sean los correspondientes a la suborden grande
                lockGetKeys.acquire()
                
                # Se obtiene la longitud de la suborden en formato de texto
                index = len(subordenG['part_id'].split('-')[1])

                # Se obtiene el entero representativo del número de suborden actual en relación a su orden padre
                subordenIndex = int(subordenG['part_id'][-index:])
                
                # Se obtiene la llave de la orden a la que pertenece
                key = int(subordenG['part_id'].split('-')[0])

                # Se obtene la orden completa a la que pertenece la suborden
                ordenCompleta = OrdersInProcessDictionary[key]
                
                # Se l
                lockGetKeys.release()
                
                # Se regresa al response el log de la suborden de QOGH en proceso
                responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOGH)".format(subordenG['part_id']))
                
                # Se calcula la cantidad de tacos por hacer de la suborden grande
                cantTacosPorHacer = math.floor(subordenG['quantity'] / 4)
                
                # En base al siguiente condicional aseguramos que cada suborden siempre sea completada en exactamente 4 repeticiones
                if(OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] / cantTacosPorHacer < 2):
                    cantTacosPorHacer = OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos']
                
                # Por cada taco que se va a realizar
                for tacos in range(cantTacosPorHacer): 
                    # Se llama la función de cookFood para realizar el taco
                    cookFood(taquero, subordenG, key, subordenIndex )
                    
                    # Se actualiza la información de metadata para el visualizador y se envía
                    info[subordenG['part_id']] = [subordenG["part_id"], subordenG["type"], subordenG["meat"], subordenG["remaining_tacos"]]
                    sendMetadata()
                    
                    # Esta funcion se llama y el taquero decide si es momento de descansar en base a la cantidad de tacos que lleva
                    if taquero.rest(): 
                        # Si si descansa entonces se agrega la respuesta de que dicho taquero descansó
                        responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(taquero.id))
                
                # Si la cantidad de tacos restantes por hacer de la suborden en el diccionario de ordenes en proceso es 0
                if (OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] == 0):
                    # Si la suborden grande es de quesadillas
                    if subordenG['type'] == TYPES[TYPES.index('quesadilla')]:
                        # Se crea una petición de quesadillas para realizar la suborden (no para rellenar el stack)
                        subordenQues = (subordenG, taquero.id, 0)
                        
                        # Se manda la petición al quesadillero
                        queueQuesadillas.append(subordenQues)
                    else:
                        # Se elimina de la metadata ta la dubórden completada
                        info.pop(subordenG['part_id'])
                        
                        # Establecemos en el diccionario de ordenes en proceso el estado de la suborden como EXIT
                        OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                        
                        # Se le regresa al response el log de la suborden completada
                        responseOrden(key, ordenCompleta, who, "Suborden {0} es completada".format(subordenG['part_id']))
                        mergeFinishedOrders(key)
                    
                    if (len(taquero.QOGE)>0):
                        taquero.QOGH.append(taquero.QOGE.pop())
                else:
                    # Si la suborden grande no ha sido completada se reingresa al QOGH para luego hacerse en la siguiente iteración
                    OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[1]
                    taquero.QOGH.append(subordenG)

# Se crea un lock para asegurar que se actualicen correctamente los ingredientes, cantidad de tacos restantes  y respuesta
lockHacerTaco = threading.Lock()

def cookFood(taquero, suborder, key, subordenIndex):
    
    # Cuando se hace un taco se cambia el estado a RUNNING de la suborden correspondiente
    OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[2]

    # Se obtiene el nombre taquero que está realizando el taco
    who = "taquero" + str(taquero.id)
    print(f"{who} haciendo un taco de {suborder['part_id']}")
    # El taquero se tarda 1 segundo en hacer un taco
    sleep(1)
    
    # Variables necesarias para actualizar las acciones de la orden
    lockHacerTaco.acquire()

    # Objeto que representa la orden padre de la suborden actual
    ordenCompleta = OrdersInProcessDictionary[key]
    
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
        # Tiempo que demora el taquero en agregar cada filling
        sleep(TAQUERO_WAITING_TIME[ing])  
        taquero.fillings[ing] -= 1
    
    # Siempre que el taquero hace un taco se utiliza una tortilla y el counter del taquero incrementa
    taquero.fillings["tortillas"] -=1        
    taquero.tacoCounter += 1
    
    # Restamos la cantidad de restantes de tacos por uno
    OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] -=1
    info[suborder['part_id']] = [suborder["part_id"], suborder["type"], suborder["meat"], suborder["remaining_tacos"]]
    lockHacerTaco.release()

# PARA LOS TAQUEROS DE ASADA Y SUADERO
# Se crea un lock para asegurar que dos taqueros estén realiando ordenes sobre un mismo queue
parallel_on_same_queue = threading.Lock()

# Se crea un lock para asegurar que dos taqueros estén realiando ordenes sobre diferentes queues 
parallel_on_different_queues = threading.Lock()

# Se instancia el lock para controlar el acceso a datos relativos a quesadillas por los taqueros de asada y suadero
quesadillasLock = threading.Lock()

# Se crea un lock para asegurar que la instancia de un taquero pueda cambiarse de flag correctamente
change_flag = threading.Lock()

# Se crea un lock para asegurar el "paralelismo" integro de los dos taqueros sobre el QOGH
parallel_on_same_queue_QOGH = threading.Lock()

# Lock generado para asegurar que al momento de hacer append al QOGH no exista context switch conflictivo
appendQOGH = threading.Lock()

# Se crea un lock para asegurar que solo se esté realizando una suborden grande por un solo taquero
cookGrande = threading.Lock()

# Se crea un lock para asegurar la integridad de la información de cada suborden pequeña al realizarla
cookSubordenPequenia = threading.Lock()

# Se define la función manejadora de la realización de tacos para los taqueros de asada y suadero, recibiendo el objeto que contiene los queues compartidos 
# y la instancia de taquero llamada por el thread
def sharedTaqueroMethod(Taquero, instance):
    # Se define el diccionario que establece el uso del stack
    stackTaken = {1: False, 2: False}
    
    # Debido a que son threads siempre están realizando está función
    while (True): 
        # Se obtiene un identificador de cuál de los dos taqueros está realizando una acción
        who = "Taquero {0}".format(instance.id)
        
        # En caso de que se tengan solamente ordenes pequeñas o solamente ordenes grandes ambos taqueros entran, si no uno se
        # queda y el otro se va a hacer lo contrario del otro taquero (Ej. Si taquero 1 está en haciendo ordenes pequeñas y solamente
        # hay ordenes pequeñas entonces ambos taqueros entran a la condicional [False], por otro lado, si además hay ordenes grandes 
        # el taquero 1 hace sus ordenes pequenias mientras que el taquero 2 hace las ordenes grandes [True])
        if parallel_on_different_queues.locked() == False:
            
            # Si el QOGH del taquero no está vacío
            if (len(Taquero.QOGH) > 0):
                parallel_on_different_queues.acquire()
                # se adquiere el lock para limitar que dos taqueros cambien sus flags al mismo tiempo
                # evitando que realizan sus tareas correspondientes (hacer tacos pequeños o grandes)
                change_flag.acquire()
                # Verifica qué instancia de taquero es la actual y cambia su bandera en caso de que el otro taquero de asada se encuentre haciendo 
                # órdenes pequeñas, en cuyo caso la actual instancia se define para hacer órdenes grandes
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == False):
                        instance.flag = True
                else:
                    if (Taquero.taquero1.flag == False):
                        instance.flag = True
                change_flag.release()

            # Comienza a iterar siempre que existan tacos pequeños por hacer en el QOP y el taquero tenga su bandera establecida
            # para hacer órdenes pequeñas
            while(len(Taquero.QOP) > 0 and instance.flag == False):
                print(f"{who} hace orden pequeña")
                
                # Cuando se tome algo del QOP se hace un acquire para asegurar que un taquero no intente sacar de un queue posiblemente vacío
                parallel_on_same_queue.acquire() 
                
                # Se instancia la variable que guardará la orden pequeña obtenida del queue
                subordenP = None
                
                # Se revisa que el Queue no esté vacío y se saca una suborden pequeña por realizar
                if len(Taquero.QOP)>0:
                    subordenP = Taquero.QOP.pop()
                
                # Cuando el taquero ya tenga su orden por hacer se hace release para que el otro tome la siguiente orden pequenia disponible
                parallel_on_same_queue.release() 
                
                # Si obtuvo una suborden pequeña del QOP
                if (subordenP is not None):
                    # Se obtiene la longitud de la suborden en formato de texto
                    index = len(subordenP['part_id'].split('-')[1])
                    
                    # Se obtiene el entero representativo del número de suborden actual en relación a su orden padre
                    subordenIndex = int(subordenP['part_id'][-index:])
                    
                    # Llave de la orden a la que pertenece y orden completa en función de la llave
                    key = int(subordenP['part_id'].split('-')[0])
                    ordenCompleta = OrdersInProcessDictionary[key]
                    
                    # Se agrega en el diccionario de respuesta la acción realizada respecto a la suborden
                    responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOP)".format(subordenP['part_id']))
                    
                    # Se realiza un acquire del lock que permite la no existencia de un context switch al momento de 
                    # determinar si la suborden actual requiere de quesadillas (ser enviada al queue de quesadillas en caso de tomar las del stack del quesadillero)
                    quesadillasLock.acquire()
                    
                    # Si la suborden pequeña es de quesadillas
                    if (subordenP['type']==TYPES[1]):
                        # Si la suborden puede ser atendida con el stack de quesadillas
                        if (subordenP['quantity'] <= instance.stackQuesadillas):
                            # Se restan las quesadillas tomadas del stack de quesadillas del quesadillero
                            instance.stackQuesadillas -= subordenP['quantity']
                            
                            # Se instancia una tupla incluyendo la descripcion de la suborden, el id del taquero actual y un identificador
                            # indicando que se requiere de un resurtido de quesadillas del stack
                            peticionQuesadillas = (subordenP , instance.id, 1)

                            # se agrega la petición al queue del quesadillero
                            queueQuesadillas.append(peticionQuesadillas)
                            # se establece que se utilizaron las quesallas del stack
                            stackTaken[instance.id] = True
                            
                    quesadillasLock.release()
                    
                    print("Suborden {0} en proceso (QOP)".format(subordenP['part_id']))
                    
                    # Por cada taco que tenga la suborden pequeña
                    for taco in range(subordenP['quantity']):
                        # Se realiza un lock para realizar el taco (garantizar la integridad de la informacioón en caso de contextt switch)
                        cookSubordenPequenia.acquire()
                        
                        # Se manda llamar la función para realizar el taco 
                        cookFood(instance, subordenP, key, subordenIndex)
                        
                        # Se agrega al diccionario de metadata la actualización del estado de la suborden y se envía la información al visualizador
                        info[subordenP['part_id']] = [subordenP["part_id"], subordenP["type"], subordenP["meat"], subordenP["remaining_tacos"]]
                        sendMetadata()
                        
                        # El taquero que haya hecho el taco revisa si es necesario descansar
                        if instance.rest(): 
                            # En caso de que sí, descansa y regresamos el response de su descanso
                            responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(instance.id))
                        
                        # Se libera el lock para que otro taquero o el mismo pueda atender el siguiente taco
                        cookSubordenPequenia.release()
                    
                    # Se adquiere el lock para garanizar que la petición de quesaillas sea la correcta
                    quesadillasLock.acquire()

                    # Si la suborden era de quesadillas y en un momento no se tomaron del stack de quesadillas para atenderla  
                    if subordenP['type']==TYPES[1] and stackTaken == False:
                        # Se crea una petición identificando que solamente es para atenderla como una suborden y no una petición de rellenado del stack
                        peticionQuesadillas = (subordenP, instance.id, 0)
                        
                        # La petición se agrega al queue del quesadillero
                        queueQuesadillas.append(peticionQuesadillas)
                        
                        # Se regresa al response el log de la suborden que fue enviada al QOP del quesadillero
                        responseOrden(key, ordenCompleta, who, "Suborden {0} enviada a quesadillero (QOP)".format(subordenP['part_id']))
                    else:
                        # Se regresa al response el log de la suborden del QOP que fue completada
                        responseOrden(key, ordenCompleta, who, "Suborden {0} es completada (QOP)".format(subordenP['part_id']))
                        
                        # En el diccionario de ordenes en proceso se establece el estado de la suborden como EXIT
                        OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]
                        
                        # Removemos la suborden completada del diccionario de metadata
                        info.pop(subordenP['part_id'])

                        # Verificamos que la orden padre de la suborden completada ya se encuentre en EXIT
                        mergeFinishedOrders(key)
                        
                    quesadillasLock.release()
                    
                    # Si el QOGH del taquero tiene uno o más subordenes
                    if len(Taquero.QOGH) > 0:  
                        # Se adquiere el lock para garanatizar un cambio del flag de la instancia correcta
                        # cambiandolo a verdadero (hacer ordenes grandes) si el otro taquero se encuentra haciendo ordenes pequeñas
                        change_flag.acquire()
                        if(Taquero.taquero1 == instance):
                            if (Taquero.taquero2.flag == False):
                                instance.flag = True
                        else:
                            if (Taquero.taquero1.flag == False):
                                instance.flag = True
                        
                        # Se libera el lock de cambio de flags 
                        change_flag.release()    

            # En orden de actualizar las banderas a la salida del while se verifica lo siguiente            
            # Si el QOGH del taquero tiene uno o más subordenes 
            if len(Taquero.QOGH) > 0: 
                # Se adquiere el lock para garanatizar un cambio del flag de la instancia correcta
                # cambiandolo a verdadero (hacer ordenes grandes) si el otro taquero se encuentra haciendo ordenes pequeñas
                change_flag.acquire()
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == False):
                        instance.flag = True
                else:
                    if (Taquero.taquero1.flag == False):
                        instance.flag = True
                
                # Se libera el lock de cambio de flags 
                change_flag.release()    
            else:
                # La instancia actual puede continuar haciendo órdenes pequeñas
                change_flag.acquire()
                instance.flag = False

                # Se libera el lock de cambio de flags 
                change_flag.release() 
                
        else: 
            print(f"{who} is at QOGH {len(Taquero.QOGH)}, {instance.flag}")
            if (len(Taquero.QOGH) > 0 and instance.flag == True):
                print(f"----------{who} hace orden grande----------------")

                # Se adquiere el lock para garantizar la integridad de los taqueros en un mismo queue
                parallel_on_same_queue_QOGH.acquire()
                
                # Se instancia una variable de subordenG en caso de que el taquero no logre sacar algo del queue (cuando está vacío)
                subordenG = None
                
                # Si el QOGH del taquero tiene uno o más
                if (len(Taquero.QOGH) > 0):
                    # Se le hace pop al QOGH y obtenemos la suborden grande
                    subordenG =  Taquero.QOGH.pop()
                parallel_on_same_queue_QOGH.release()
                
                # En caso de que se haya logrado sacar una suborden grande
                if (subordenG is not None):
                    # Se obtiene la longitud de la suborden en formato de texto
                    index = len(subordenG['part_id'].split('-')[1])
                    
                    # Se obtiene el entero representativo del número de suborden actual en relación a su orden padre
                    subordenIndex = int(subordenG['part_id'][-index:])

                    # Llave de la orden a la que pertenece y orden completa en función de la llave
                    key = int(subordenG['part_id'].split('-')[0])
                    ordenCompleta = OrdersInProcessDictionary[key]
                    
                    # Regresamos al response el log de la suborden de QOGH que se encuentra en proceso
                    responseOrden(key, ordenCompleta, who, "Suborden {0} en proceso (QOGH)".format(subordenG['part_id']))
                    
                    # Obtenemos la octava parte redondeada al entero mayor o igual más próximo 
                    cantTacosPorHacer = math.floor(subordenG['quantity'] / 8)

                    # Se verifica que se puedan realizar más de una iteración, si no es posible se toman todos los tacos 
                    # restantes como "por hacer" en la iteracion actual
                    if(OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] / cantTacosPorHacer < 2):
                        cantTacosPorHacer = OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos']
                    
                    # Por cada taco de la fracción de la suborden grande
                    for tacos in range(cantTacosPorHacer): 
                        # Se obtiene un lock para asegurar que solo taquero haga el taco
                        cookGrande.acquire()

                        # Se manda a llamar la función para hacer el taco
                        cookFood(instance, subordenG, key, subordenIndex)

                        # Se agrega al diccionario de metadata la actualización del estado de la suborden y se envía la información al visualizador
                        info[subordenG['part_id']] = [subordenG["part_id"], subordenG["type"], subordenG["meat"], subordenG["remaining_tacos"]]
                        sendMetadata()
                        
                        # El taquero que haya hecho el taco revisa si es necesario descansar y se adjunta al diccionario de respuestas en caso de haber descansado
                        if instance.rest(): 
                            responseOrden(key, ordenCompleta, who, "El taquero {0} ha descansado".format(instance.id))
                        
                        # Se libera el lock para permitir al otro taquero o a si mismo de hacer otro taco
                        cookGrande.release()
                        
                        # Si QOP tiene una o más subordenes, se verifican los flags de la otra instancia del taquero y se actualizan
                        # si la otra instancia se encuentra haciendo tacos grandes, la actual cambia su bandera para hacer tacos grandes
                        if (len(Taquero.QOP)>0):
                            change_flag.acquire()
                            
                            # Se adquiere el lock para garanatizar un cambio del flag de la instancia correcta
                            # cambiandolo a verdadero (hacer ordenes grandes) si el otro taquero se encuentra haciendo ordenes pequeñas
                            if(Taquero.taquero1 == instance):
                                if (Taquero.taquero2.flag == True):
                                    instance.flag = False
                                    
                                    # Para que los taqueros puedan dividirse las cargas de nuevo de los queues se realiza lo siguiente
                                    if parallel_on_different_queues.locked():
                                        parallel_on_different_queues.release()
                            else:
                                if (Taquero.taquero1.flag == True):
                                    instance.flag = False
                                    
                                    # Para que los taqueros puedan dividirse las cargas de nuevo de los queues se realiza lo siguiente
                                    if parallel_on_different_queues.locked():
                                        parallel_on_different_queues.release()
                                        
                            change_flag.release()
                    
                    # Se hace acquire de un lock para que solo uno maneje la actualizacion de respuestas y llamados de peticiones de quesadillas
                    appendQOGH.acquire()
                    
                    # Si la cantidad de tacos restantes de la suborden es igual a 0
                    if (OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] == 0):
                        # Si la subordenG es de quesadillas se le hace append la suborden a la queue de quesadillas
                        if subordenG['type'] == TYPES[TYPES.index('quesadilla')]:
                            # Se crea una petición identificando que solamente es para atenderla como una suborden y no una petición de rellenado del stack
                            subordenQues = (subordenG, instance.id, 0)
                            
                            # La petición se agrega al queue del quesadillero
                            queueQuesadillas.append(subordenQues)
                        else:
                            # Dado que la subórden es de tacos y ya está terminada, se eliminar de la metadata a enviar al voisualizador
                            info.pop(subordenG['part_id'])

                            # Se actualiza el estado de la suborden como EXIT (terminado)
                            OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[3]

                            # Se reaiza el log correspondiente en el diccionario
                            responseOrden(key, ordenCompleta, who, "Suborden {0} es completada".format(subordenG['part_id']))
                            # Se verifica que la orden padre ya haya sido completamente terminada
                            mergeFinishedOrders(key)
                        if (len(Taquero.QOGE)>0):
                            # Si el QOGE posee subórdenes dentro (no está vacío) se toma dicha orden y se agrega al QOGH 
                            print(f"QOGE -----> QOGH  {len(Taquero.QOGE)}")
                            Taquero.QOGH.append(Taquero.QOGE.pop())
                    else:
                        # Si la suborden grande de tacos no ha sido completada se reingresa al QOGH para que sea continuada 
                        print(f"subordenG -----> QOGH, restantes: {OrdersInProcessDictionary[key]['orden'][subordenIndex]['remaining_tacos'] }")
                        OrdersInProcessDictionary[key]['orden'][subordenIndex]['status'] = STATES[1]
                        Taquero.QOGH.append(subordenG)  
                    appendQOGH.release()
 
            # Si existen subórdenes dentro del QOP se verifican los flags con el fin de actualizarlos
            if (len(Taquero.QOP)>0):
                change_flag.acquire()
                
                # Se adquiere el lock para garanatizar un cambio del flag de la instancia correcta
                # cambiandolo a verdadero (hacer ordenes grandes) si el otro taquero se encuentra haciendo ordenes pequeñas
                if(Taquero.taquero1 == instance):
                    if (Taquero.taquero2.flag == True):
                        instance.flag = False
                        
                        # Para que los taqueros puedan dividirse las cargas de nuevo de los queues se realiza lo siguiente
                        if parallel_on_different_queues.locked():
                            parallel_on_different_queues.release()
                else:
                    if (Taquero.taquero1.flag == True):
                        instance.flag = False
                        
                        # Para que los taqueros puedan dividirse las cargas de nuevo de los queues se realiza lo siguiente
                        if parallel_on_different_queues.locked():
                            parallel_on_different_queues.release()

                change_flag.release()  
            else:
                # En caso contrario continua haciendo órdenes grandes
                change_flag.acquire()
                instance.flag = True
                change_flag.release()  
            
            # Para que los taqueros puedan dividirse las cargas de nuevo de los queues se realiza lo siguiente
            if parallel_on_different_queues.locked():   
                parallel_on_different_queues.release()



# Calcula el porcentaje de existencias de determinado ingrediente para un taquero dado, recibiendo la cantidad actual 
# y el indice del ingrediente a consultar
def porcentaje(actual,indice):
    return actual / INGREDIENTS_AT_MAX[list(INGREDIENTS_AT_MAX.keys())[indice]]

def chalanArriba():        
    # Debido a que el chalan es un thread, siempre esta realizando esta función
    while True:
        # Genera un lista de tuplas conteniendo el filling y su número (del 0 al 4)
        ingredientsA = [(taqueroAdobada.fillings[ingredient],i) for ingredient,i in zip(list(taqueroAdobada.__dict__['fillings']), range(0,5))]
        ingredientsS = [(taqueroAsadaSuadero.taquero1.fillings[ingredient],i) for ingredient,i in zip(list(taqueroAsadaSuadero.taquero1.__dict__['fillings']), range(0,5))]
        
        # Se inicializa la lista conteniendo los valores para los taqueros que serán servidos por este chalan
        fillingsList = [ingredientsA,ingredientsS]
        
        # Se actualiza la lista insertando una tupla con tres elementos en la que se contiene el porcentaje de existencias de determinado
        # filling (e.g. 0.95 existencias de tortillas para taqeuro de adobada) y su correspondiente indice
        fillingsList[0] = [ (porcentaje(tupleInfo[0], fillingsList[0].index(tupleInfo)), tupleInfo[1]) for tupleInfo in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(tupleInfo[0], fillingsList[1].index(tupleInfo)), tupleInfo[1]) for tupleInfo in fillingsList[1] ]
        
        # Se revisa el ingrediente mínimo de los dos taqueros que atiende el chalán para identificar a cuál rellenar primero
        if min(fillingsList[0]) >= min(fillingsList[1]):
            # Si el ingrediente mínimo es del taquero 1 de asada suadero se asigna como un task por hacer (rellenado de ingrediente)
            do = min(fillingsList[1])
            
            # Si el ingrediente mínimo del taquero 1 de asada suadero está bajo del 100% de capacidad
            if do[0] < 1.0:
                # En base al ingrediente mínimo se identifica el nombre del ingrediente a rellenar
                which = list(taqueroAsadaSuadero.taquero1.__dict__['fillings'])[do[1]]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero1.id))
                
                # Se establece la espera durante el tiempo predeterminado que le toma al halan rellenar determinado filling
                sleep(CHALAN_WAITING_TIME[which])
                
                # Se reestablece el ingrediente mínimo del taquero a su cantidad máxima
                taqueroAsadaSuadero.taquero1.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero1.id))
        else:
            # Si el ingrediente mínimo es del taquero de adobada se asigna como un task por hacer (rellenado de ingrediente)
            do = min(fillingsList[0])
            
            # Si el ingrediente mínimo del taquero de adobada está bajo del 100% de capacidad
            if do[0] < 1.0: 
                # En base al ingrediente mínimo se identifica el nombre del inggrediente por rellenar
                which = list(taqueroAdobada.__dict__['fillings'])[do[1]]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAdobada.id))
        
                # Se establece la espera durante el tiempo predeterminado que le toma al halan rellenar determinado filling
                sleep(CHALAN_WAITING_TIME[which])
                
                # Se reestablece la cantidad del ingrediente mínimo del taquero a su cantidad máxima
                taqueroAdobada.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAdobada.id))
        
        # Cada iteración del while del chalán manda a llamar una actualización de los ingredientes de cada taquero
        sendMetadata()
            
def chalanAbajo():
    # Debido a que el chalan es un thread, siempre esta realizando esta función
    while True:
        # Genera un lista de tuplas conteniendo el filling y su número (del 0 al 4)
        ingredientsT = [(taqueroTripaCabeza.fillings[a],i) for a,i in zip(list(taqueroTripaCabeza.__dict__['fillings']), range(0,5))]
        ingredientsS= [(taqueroAsadaSuadero.taquero2.fillings[a],i) for a,i in zip(list(taqueroAsadaSuadero.taquero2.__dict__['fillings']), range(0,5))]
        
        # se inicializa la lista conteniendo los valores para los taqueros que serán servidos por este chalan
        fillingsList = [ingredientsT, ingredientsS]
        # Se actualiza la lista insertando una tupla con tres elementos en la que se contiene el porcentaje de existencias de determinado
        # filling (e.g. 0.95 existencias de tortillas para taquero de tripa y cabeza) y su correspondiente indice
        fillingsList[0] = [ (porcentaje(a[0], fillingsList[0].index(a)), a[1]) for a in fillingsList[0] ]
        fillingsList[1] = [ (porcentaje(a[0], fillingsList[1].index(a)), a[1]) for a in fillingsList[1] ]

        # Se revisa el ingrediente mínimo de los dos taqueros que atiende el chalán para identificar a cuál rellenar primero
        if min(fillingsList[0]) >= min(fillingsList[1]):
            do = min(fillingsList[1])
            # Si el ingrediente mínimo del taquero 1 de asada suadero está bajo del 100% de capacidad
            if do[0] < 1.0:
                # En base al ingrediente mínimo se identifica el nombre del ingrediente a rellenar
                which = list(taqueroAsadaSuadero.taquero2.__dict__['fillings'])[do[1]]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero2.id))
            
                # Se establece la espera durante el tiempo predeterminado que le toma al halan rellenar determinado filling
                sleep(CHALAN_WAITING_TIME[which])

                # Se reestablece la cantidad del ingrediente mínimo del taquero a su cantidad máxima
                taqueroAsadaSuadero.taquero2.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroAsadaSuadero.taquero2.id))
        else:
            # Si el ingrediente mínimo es del taquero de adobada se asigna como un task por hacer (rellenado de ingrediente)
            do = min(fillingsList[0])

            # Si el ingrediente mínimo del taquero de adobada está bajo del 100% de capacidad
            if do[0] < 1.0:
                # En base al ingrediente mínimo se identifica el nombre del inggrediente por rellenar
                which = list(taqueroTripaCabeza.__dict__['fillings'])[do[1]]
                print("Chalan abajo rellenando {0} para taquero {1}".format(which, taqueroTripaCabeza.id))
                
                # Se establece la espera durante el tiempo predeterminado que le toma al halan rellenar determinado filling
                sleep(CHALAN_WAITING_TIME[which])

                # Se reestablece la cantidad del ingrediente mínimo del taquero a su cantidad máxima
                taqueroTripaCabeza.fillings[which] = INGREDIENTS_AT_MAX[which]
                print("Chalan abajo rellenó {0} para taquero {1}".format(which, taqueroTripaCabeza.id))
       
        # Cada iteración del while del chalán manda a llamar una actualización de los ingredientes de cada taquero
        sendMetadata()

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

# Función que se encarga de mandar la orden a un categorizador
def readJson(orden):
    # Inicializa la orden dentro del diccionario de ordenes, estableciendo como llave su request id
    OrdersInProcessDictionary[orden['request_id']] = orden
    # Manda orden a categorizador
    categorizador(orden, orden['request_id'])

# Thread Lock para dejar que un solo thread lea a la vez    
sqsLock = threading.Lock()
# Se tiene un cliente que "ordena a la taquería" generando así ordemes que atender
def cliente1():
    while True:
        # Se obtiene el mensaje y la orden leídos del SQS enviando la instancia de sqs y el url del queue correspondiente
        msg, orden = handler.read_message(sqs, queue_url)
        # En caso de que sí haya un mensaje de una orden que atender, se borra el mensaje y se manda para que la taquería atienda la orden leída
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            # Se establce el uso de un lock para que solamente un cliente pueda hacer acceso a la escritura de los queues internos de la taqueria
            sqsLock.acquire()
            readJson( orden)
            sqsLock.release()

# En caso de leer de más de un SQS se tiene una función similar a la del cliente1 pero relacionado con el sqs correspondiente
def cliente2():
    while True:
        msg, orden = handler.read_message(sqs, queue_url)
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            sqsLock.acquire()
            readJson(orden)
            sqsLock.release()

# En caso de leer de más de un SQS se tiene una función similar a la del cliente1 pero relacionado con el sqs correspondiente
def cliente3():
    while True:
        msg, orden = handler.read_message(sqs, queue_url)
        if (msg!=None):
            handler.delete_message(msg, orden, sqs, queue_url)
            sqsLock.acquire()
            readJson(orden)
            sqsLock.release()

# Cada vez que se realice un taco (de cualquier taquero) se actualiza la información del visualizador
def sendMetadata():
    # Data contiene la metadata de cada uno de los cuatro taqueros de la taqueria en forma de diccionario
    data = { "0":[taqueroAdobada.id, taqueroAdobada.tacoCounter, taqueroAdobada.fillings["salsa"], taqueroAdobada.fillings["guacamole"], taqueroAdobada.fillings["cebolla"], taqueroAdobada.fillings["cilantro"], taqueroAdobada.fillings["tortillas"], taqueroAdobada.stackQuesadillas, taqueroAdobada.fan, taqueroAdobada.tacoCounter%taqueroAdobada.tacosNeededForRest == 0 ],
    "1":[taqueroAsadaSuadero.taquero1.id, taqueroAsadaSuadero.taquero1.tacoCounter, taqueroAsadaSuadero.taquero1.fillings["salsa"], taqueroAsadaSuadero.taquero1.fillings["guacamole"], taqueroAsadaSuadero.taquero1.fillings["cebolla"], taqueroAsadaSuadero.taquero1.fillings["cilantro"], taqueroAsadaSuadero.taquero1.fillings["tortillas"], taqueroAsadaSuadero.taquero1.stackQuesadillas, taqueroAsadaSuadero.taquero1.fan, taqueroAsadaSuadero.taquero1.tacoCounter%taqueroAsadaSuadero.taquero1.tacosNeededForRest == 0 ],
    "2":[taqueroAsadaSuadero.taquero2.id, taqueroAsadaSuadero.taquero2.tacoCounter, taqueroAsadaSuadero.taquero2.fillings["salsa"], taqueroAsadaSuadero.taquero2.fillings["guacamole"], taqueroAsadaSuadero.taquero2.fillings["cebolla"], taqueroAsadaSuadero.taquero2.fillings["cilantro"], taqueroAsadaSuadero.taquero2.fillings["tortillas"], taqueroAsadaSuadero.taquero2.stackQuesadillas, taqueroAsadaSuadero.taquero2.fan, taqueroAsadaSuadero.taquero2.tacoCounter%taqueroAsadaSuadero.taquero2.tacosNeededForRest == 0 ],
    "3":[taqueroTripaCabeza.id, taqueroTripaCabeza.tacoCounter, taqueroTripaCabeza.fillings["salsa"], taqueroTripaCabeza.fillings["guacamole"], taqueroTripaCabeza.fillings["cebolla"], taqueroTripaCabeza.fillings["cilantro"], taqueroTripaCabeza.fillings["tortillas"], taqueroTripaCabeza.stackQuesadillas, taqueroTripaCabeza.fan, taqueroTripaCabeza.tacoCounter%taqueroTripaCabeza.tacosNeededForRest == 0]}
    
    # Se envía la metadata a su función correspondiente
    sendToNode(data, info, currentQuesadilla)

# Instancia del SQS handler 
handler = SQS_handler()

# Instancia de los queues que cada taquero tiene
instanceQueues = queues()

# Instancias de taqueros con su tiempo de descanso, cuántos tacos necesita para descansar y su id
taqueroAdobada = taqueroIndividual(3, 100, 0)
taqueroTripaCabeza = taqueroIndividual(3, 100, 3)
taqueroAsadaSuadero = taquerosShared(9.33, 9.39, 1, 2)

# Agrega los queues requeridos a las instancias de taquero de adobada y taquero de tripa y cabeza
taqueroAdobada.__dict__.update(instanceQueues.__dict__)
instanceQueues = queues()
taqueroTripaCabeza.__dict__.update(instanceQueues.__dict__)

# se definen las variables que serviran para enviar la metadata al visualizador
info = {}
currentQuesadilla = []

# Función de inicio de la taquería
if __name__ == "__main__":
    # THREADS DE LOS CHALANES
    chalanArribaThread = Thread(target=chalanArriba, args=())
    chalanAbajoThread = Thread(target=chalanAbajo, args=())

    # THREAD DE QUESADILLERO
    quesadilleroThread = Thread(target=quesadillero, args=())
    
    # THREADS DE LOS LISTENERS DE SQS
    sqs_listener1 = Thread(target=cliente1, args=())
    sqs_listener2 = Thread(target=cliente2, args=())
    sqs_listener3 = Thread(target=cliente3, args=()) 

    # THREADS DE TAQUEROS INDIVIDUALES
    adobadaThread = Thread(target=individualTaqueroMethod, args=(taqueroAdobada,))
    tripaCabezaThread = Thread(target=individualTaqueroMethod, args=(taqueroTripaCabeza,))
    
    # THREADS DE TAQUEROS SHARED
    uno = Thread(target=sharedTaqueroMethod, args=(taqueroAsadaSuadero, taqueroAsadaSuadero.taquero1))
    dos = Thread(target=sharedTaqueroMethod, args=(taqueroAsadaSuadero, taqueroAsadaSuadero.taquero2))

    # THREADS PARA VENTILADORES DE CADA TAQUERO
    threadVentilador1 = threading.Thread(target=fan_, args=(taqueroAdobada,))
    threadVentilador2 = threading.Thread(target=fan_, args=(taqueroTripaCabeza,))
    threadVentilador3 = threading.Thread(target=fan_, args=(taqueroAsadaSuadero.taquero1,))
    threadVentilador4 = threading.Thread(target=fan_, args=(taqueroAsadaSuadero.taquero2,))
    
    # THREAD STARTS
    uno.start()
    dos.start()
    adobadaThread.start()
    tripaCabezaThread.start()
    chalanArribaThread.start()
    chalanAbajoThread.start()
    quesadilleroThread.start()
    sqs_listener1.start()
    sqs_listener2.start()
    sqs_listener3.start()
    threadVentilador1.start()
    threadVentilador2.start()
    threadVentilador3.start()
    threadVentilador4.start()

    # THREAD JOINS
    chalanArribaThread.join()
    chalanAbajoThread.join()
    quesadilleroThread.join()
    uno.join()
    dos.join()
    adobadaThread.join()
    tripaCabezaThread.join()
    sqs_listener1.join()
    sqs_listener2.join()
    sqs_listener3.join()
    threadVentilador1.join()
    threadVentilador2.join()
    threadVentilador3.join()
    threadVentilador4.join()