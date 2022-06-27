#messageTriggeredSender
import json
import re
import boto3
import os
import time
from datetime import datetime

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

SOURCE_EMAIL= os.environ['SOURCE_EMAIL']
LAST_CONTACT_TABLE= os.environ['LAST_CONTACT_TABLE']


def lambda_handler(event, context):
    print(event)

    for record in event['Records']:
        message = json.loads(record['Sns']['Message'])
        if('originationNumber' in message):
            phone = str(message['originationNumber'])
            customerEmail = str(message['messageBody'])
            
            if(validate_email(customerEmail)):
                print("Valid email")
                contact = get_contact_details(phone,LAST_CONTACT_TABLE)
                if(contact):
                    print("Contact")
                    print(contact)
                    
                    contactDate = get_contact_date(contact['contactId'],contact['instanceId'])

                    print('contactDate')
                    print(contactDate)
                    
                    print('contactId: ' + contact['contactId'])
                    transcript = get_transcript(contact['contactId'],contactDate,contact['channel'],contact['instanceId'])
                    print("phone:" + phone)
                    print("email:" + customerEmail)
                    print("transcript:" + transcript)

                    send_email(customerEmail,SOURCE_EMAIL,'Conversation',transcript)
            else:
                print("not valid")
                


    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def get_contact_date(contactId,instanceId):
    try: 
        connect_client = boto3.client("connect")
        response = connect_client.describe_contact(
            InstanceId=instanceId,
            ContactId=contactId
            )
    except ClientError as e:
        print(e.response['Error']['Message'])
        return None
    else:
        contactDate = {}
        contactDate['year'] = str(response['Contact']['InitiationTimestamp'].year)
        contactDate['month'] = str(response['Contact']['InitiationTimestamp'].month).zfill(2)
        contactDate['day'] = str(response['Contact']['InitiationTimestamp'].day).zfill(2)
        return contactDate


def validate_email(email):
   pat = "^[a-zA-Z0-9-_]+@[a-zA-Z0-9]+\.[a-z]{1,3}$"
   if re.match(pat,email):
      return True
   return False

def get_contact_details(phone,table):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table)
    response = table.query(
        KeyConditionExpression=Key('phone').eq(phone)
    )
    contact={}
    if(response['Items']):
        contact['contactId'] =response['Items'][0]['contactId']
        contact['instanceId'] =response['Items'][0]['instanceId']
        contact['channel'] =response['Items'][0]['channel']
    else:
        contact=None
    
    return contact

def get_transcript(contactId,contactDate,contactChannel,instanceId):
    s3 = boto3.resource('s3')
    bucketConfig = get_instance_storage_config(instanceId,contactChannel)
    
    bucket = s3.Bucket(bucketConfig['BucketName'])
    bucketPrefix = bucketConfig['BucketPrefix']+contactDate['year']+'/'+contactDate['month']+'/'+contactDate['day']+'/'+contactId
    numberObjects = sum(1 for _ in bucket.objects.filter(Prefix=bucketPrefix))
    
    if(numberObjects >= 1):
        print("Transcript already available")
    else:
        print("No transcript available, waiting 10")
        time.sleep(10)
        print("Finished waiting")
    
    transcript= ''
    for s3object in bucket.objects.filter(Prefix=bucketConfig['BucketPrefix']+contactDate['year']+'/'+contactDate['month']+'/'+contactDate['day']+'/'+contactId):
        fileContent = s3object.get()['Body'].read().decode('utf-8')
        jsonContent = json.loads(fileContent)
        for turn in jsonContent['Transcript']:
            if(contactChannel=='VOICE') and 'Content' in turn:
                transcript += turn['ParticipantId']+':'+ turn['Content'] +'\n'
            if(contactChannel=='CHAT') and 'Content' in turn:
                transcript += turn['ParticipantRole']+':'+ turn['Content'] +'\n'
    return transcript

def send_email(destination,source,subject, content):
    ses_client = boto3.client("ses")
    CHARSET = "UTF-8"
    response = ses_client.send_email(
        Destination={
            "ToAddresses": [
                destination,
            ],
        },
        Message={
            "Body": {
                "Text": {
                    "Charset": CHARSET,
                    "Data": content,
                }
            },
            "Subject": {
                "Charset": CHARSET,
                "Data": subject,
            },
        },
        Source=source
    )

def get_instance_storage_config(instanceId,contactChannel):
    connect_client = boto3.client('connect')
    storageConfig = None
    bucketConfig = ''
    if(contactChannel == 'VOICE'):
        storageConfig = connect_client.list_instance_storage_configs(InstanceId=instanceId,ResourceType='CALL_RECORDINGS')
        bucketConfig = storageConfig['StorageConfigs'][0]['S3Config']
        bucketConfig['BucketPrefix']='Analysis/Voice/'
        
    elif(contactChannel== 'CHAT'):
        storageConfig = connect_client.list_instance_storage_configs(InstanceId=instanceId,ResourceType='CHAT_TRANSCRIPTS')
        bucketConfig = storageConfig['StorageConfigs'][0]['S3Config']
        bucketConfig['BucketPrefix']+='/'
    if(storageConfig):
        return bucketConfig
    else:
        return None