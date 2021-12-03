import requests
  
def sendToNode(taqueros, orders, quesadillas):
    data = {'taqueros': taqueros, "orders":orders, "quesas":quesadillas}
    res = requests.post('http://127.0.0.1:3001/status', json=data) 

