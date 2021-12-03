from AWS.RoundRobin import SQS_handler
from AWS.tacos import orderGenerator as GENERATOR
import boto3
import time
sqs = boto3.client("sqs")
queue_url = "https://sqs.us-east-1.amazonaws.com/292274580527/sqs_cc106_team_7"

handler = SQS_handler()
generator = GENERATOR()


message = generator.generateOrder()

for orden in message:
    handler.write_message(orden, sqs, queue_url)
'''
msg, orden = handler.read_message(sqs, queue_url)
while msg is not None:
    handler.delete_message(msg, orden, sqs, queue_url)
    msg, orden = handler.read_message(sqs, queue_url)
'''
print(handler.get_number_messages(sqs, queue_url))
print('done')
