import requests
  
# Se define la función que interactúa con el front end (visualizador)
# recibiendo la metadata de los taqueros, las ordenes activas y el quesadillero
def sendToNode(taqueros, orders, quesadillas):
    # genera un diccionario can la metdata recibida
    data = {'taqueros': taqueros, "orders":orders, "quesas":quesadillas}
    # Realiza un post hacia la dirección local del visualizador enviando el diccionario de metadata
    res = requests.post('http://127.0.0.1:3001/status', json=data) 

