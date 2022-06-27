#ImmediateSender
import json
import boto3
from datetime import datetime
import os
import time

from botocore.exceptions import ClientError

SOURCE_EMAIL= os.environ['SOURCE_EMAIL']
LAST_CONTACT_TABLE= os.environ['LAST_CONTACT_TABLE']
PINPOINT_NUMBER = os.environ['PINPOINT_NUMBER']
MESSAGE_TEMPLATE= os.environ['MESSAGE_TEMPLATE']

def lambda_handler(event, context):
    print("Event")
    print(event)
    
    if ('detail' in event and event['detail']['actionName']=='SendConversation'):
        contactId=event['detail']['contactArn'].split('/')[-1] #Split ARN and pull last item
        instanceId=event['detail']['instanceArn'].split('/')[-1] #Split ARN and pull last item
        contactDate = get_date(event['time'])
        contactAttributes = get_contact_attributes(contactId,instanceId)
        contactChannel = 'VOICE'
        print(contactAttributes)
        
        if('email' in contactAttributes):
            transcript = get_transcript(contactId,contactDate,contactChannel,instanceId)
            send_email(contactAttributes['email'],SOURCE_EMAIL,'Conversation',transcript)
        else:
            print('No email found, asking for one')
            if('phone' in contactAttributes):
                update_contact(contactAttributes['phone'],contactAttributes['contactId'],instanceId,contactChannel,LAST_CONTACT_TABLE)
                send_sms(PINPOINT_NUMBER,contactAttributes['phone'],MESSAGE_TEMPLATE+'sms:+'+PINPOINT_NUMBER)
            else:
                print("No phone was provided, add user defined attribute 'phone' in contact flow")
                
    elif('Details' in event and event['Details']['ContactData']['Channel']=='CHAT'):
        
        instanceId = event['Details']['ContactData']['InstanceARN'].split('/')[-1] #Split ARN and pull last item
        contactId=event['Details']['ContactData']['InitialContactId']
        contactAttributes = get_contact_attributes(contactId,instanceId)
        
        contactDate = get_contact_date(contactId,instanceId)
        contactChannel = 'CHAT'
        
        if('email' in event['Details']['ContactData']['Attributes'] and event['Details']['ContactData']['Attributes']['email'] != ''):
            email=event['Details']['ContactData']['Attributes']['email']
            transcript = get_transcript(contactId,contactDate,'CHAT',instanceId)
            send_email(email,SOURCE_EMAIL,'Conversation',transcript)
        else:
            print('No email found, asking for one')
            if('phone' in event['Details']['ContactData']['Attributes'] and event['Details']['ContactData']['Attributes']['phone'] != ''):
                phone=event['Details']['ContactData']['Attributes']['phone']
                update_contact(phone,contactAttributes['contactId'],instanceId,contactChannel,LAST_CONTACT_TABLE)
                send_sms(PINPOINT_NUMBER,contactAttributes['phone'],MESSAGE_TEMPLATE+'sms:+'+PINPOINT_NUMBER)
            else:
                print("No phone was provided, add user defined attribute 'phone' in contact flow")        
        
        
        
        
        
        
    return {
        'statusCode': 200,
        'body': json.dumps('Transcription sent.')
    }
    

def get_date(timestamp):
    contactTime = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
    contactDate = {}
    contactDate['year'] = str(contactTime.year)
    contactDate['month'] = str(contactTime.month).zfill(2)
    contactDate['day'] = str(contactTime.day).zfill(2)
    return contactDate


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

def get_contact_attributes(contactId,instanceId):
    connect_client = boto3.client('connect')
    contactAttributes = {}
    
    contact = connect_client.describe_contact(
    InstanceId=instanceId,
    ContactId=contactId
    )
    print("Contact")
    print(contact)
    if ('InitialContactId'in contact['Contact']):
        contactAttributes['contactId'] = contact['Contact']['InitialContactId']
    else:
        contactAttributes['contactId'] = contact['Contact']['Id']
    
    attributes = connect_client.get_contact_attributes(
    InstanceId=instanceId,
    InitialContactId=contactAttributes['contactId']
    )
    
    
    
    if 'email' in attributes['Attributes'] and attributes['Attributes']['email']:
        print("Found email")
        contactAttributes['email'] = attributes['Attributes']['email']

    if 'phone' in attributes['Attributes'] and attributes['Attributes']['phone']:
        print("Found phone")
        contactAttributes['phone'] = attributes['Attributes']['phone']

    return contactAttributes

def update_contact(phone,contactId,instanceId,channel,lastContactTable):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(lastContactTable)
    
    try:
        response = table.update_item(
            Key={
                'phone': phone
            }, 
            UpdateExpression='SET #item = :newState, #item2 = :newState2, #item3 = :newState3',  
            ExpressionAttributeNames={
                '#item': 'contactId',
                '#item2': 'instanceId',
                '#item3': 'channel'
            },
            ExpressionAttributeValues={
                ':newState': contactId,
                ':newState2': instanceId,
                ':newState3': channel
            },
            ReturnValues="UPDATED_NEW")
        print (response)
    except Exception as e:
        print (e)
    else:
        return response


def send_sms(originPhone,destinationPhone,msg):
    pinpoint_client = boto3.client('pinpoint-sms-voice-v2',region_name='us-east-1') ##Requires new version of boto3
    
    try:
        response = pinpoint_client.send_text_message(
            DestinationPhoneNumber=destinationPhone,
            OriginationIdentity=originPhone,
            MessageBody=msg,
            MessageType='TRANSACTIONAL'
            )
        
    except ClientError as e:
        print(e.response['Error']['Message'])
        return None
    else:
        print("Message sent! Message ID: "
                + response['MessageId'])
        return response['MessageId']

def get_transcript(contactId,contactDate,contactChannel,instanceId):
    s3 = boto3.resource('s3')
    bucketConfig = get_instance_storage_config(instanceId,contactChannel)
    
    bucket = s3.Bucket(bucketConfig['BucketName'])
    bucketPrefix = bucketConfig['BucketPrefix']+contactDate['year']+'/'+contactDate['month']+'/'+contactDate['day']+'/'+contactId
    numberObjects = sum(1 for _ in bucket.objects.filter(Prefix=bucketPrefix))
    
    
    while numberObjects < 1: 
        print("No transcript available, waiting 10")
        time.sleep(10)
        numberObjects = sum(1 for _ in bucket.objects.filter(Prefix=bucketPrefix))
    else:
        print("Transcript found")
    
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