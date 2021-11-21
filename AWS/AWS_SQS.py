import boto3
import json
from datetime import datetime


sqs = boto3.client("sqs")
url = "https://sqs.us-east-1.amazonaws.com/292274580527/sqs_cc106_team_7"

orden = {
        "datetime": str(datetime.now()), 
        "request_id": "1", 
        "status": "open", 
        "orden":[
            {   
                "part_id": "1-1", 
                "type": "taco", 
                "meat": "asada", 
                "status":"open", 
                "quantity": 2, 
                "ingredients":[ "salsa", "cebolla" ] 
            },
            {   
                "part_id": "1-1", 
                "type": "taco", 
                "meat": "adobada", 
                "status":"open", 
                "quantity": 5,
                "ingredients":[ "cilantro", "cebolla" ] 
            }
        ] 
    }   

json_tacos = json.dumps(orden)

response = sqs.send_message(QueueUrl=url, MessageBody=json_tacos) 
print(response)

#responseFromQ = sqs.receive_message(QueueUrl=url)
#handle = responseFromQ['Messages'][0]['ReceiptHandle']

#deleted = sqs.delete_message(QueueUrl=url, ReceiptHandle=handle)
#print(deleted)

numberOfItems = sqs.get_queue_attributes(QueueUrl=url, AttributeNames = ["ApproximateNumberOfMessages"])
print(numberOfItems)

while(True):
    responseFromQ = sqs.receive_message(QueueUrl=url)

    if "Messages" in responseFromQ:
        print(responseFromQ['Messages'][0]['Body'])