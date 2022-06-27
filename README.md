# Amazon Connect Transcript Sender

This sample code shows a mechanism to send conversation transcripts to a user after the interaction completes.
Amazon Connnect Contact Lens generates the call transcription. Amazon Connect Chat functionality generates a copy of the exchanged messages.


## Deployed resources

The project includes a cloud formation template with a Serverless Application Model (SAM) transform to deploy resources as follows:

### AWS Lambda functions

- immediateSender: Sends conversation right after interaction is completed.
- messageTriggeredSender: Allows for a user to request a conversation transcript to be sent by an SMS message. This allows for the solution to request an email to the user if it was not readily available when immediateSender function was triggered.

### AWS Lambda Layers
 - boto3latest: Latest boto3 library for AWS services interactions.

### Eventbridge rule
- contactLensRule: Eventbridge message routing from Contact Lens rules. A Contact Lens rule should be configured to publish an Eventbridge message once a Contact Lens post-call analysis is completed.

### DynamoDB Table
- LastContact: Table used in keeping track of last contactId based on phone number. Used when a conversation's email is not found on the attributes.

## Prerequisites.

1. AWS Console Access with administrator account.
1. Cloud9 IDE or AWS and SAM tools installed and properly configured with administrator credentials.
1. Verified email addresses on SES.
1. Amazon Connect Instance already set up with a queue and contact flow.
1. Amazon Connect Customer Profiles or any System of Record that has the possibility of fecth user information, specifically user's email address.
1. Amazon Pinpoint assigned number.

## Deploy the solution
1. Clone this repo.

`git clone https://github.com/aws-samples/amazon-connect-transcript-sender`

2. Build the solution with SAM.

`sam build -u` 

3. Deploy the solution.

`sam deploy -g`

SAM will ask for the name of the application (name it something relevant such as "connect-stenographer") as all resources will be grouped under it and deployment region.Reply Y on the confirmation prompt before deploying resources. SAM can save this information if you plan un doing changes, answer Y when prompted and accept the default environment and file name for the configuration.


## Configure Amazon Connect 
4. Add the immediate-Sender function on Amazon Connect from the AWS Console -> Amazon Connect -> Instance -> Contact flows -> AWS Lambda.
5. Create a contactflow with the following items and name it Disconnect-Flow. Set the Invoke AWS function to the immediate-Sender function.
![](/imgs/disconnect-contact-flow.png)

6. On the contactflow to be used for interactions handling (Sample Queue Customer can be used if none has been created) add a Set Disconnect flow block and point it to the previously created Disconnect-Flow.
7. The following attributes need to be set by the Set Contact Attributes before call is disconnected:

| attribute   | Value |  Notes |
|----------|:-------------:|:-------------:|
| phone |  User's phone | This is the user's phone. Can be set to property System->
| email | User's email | This is the email to which conversation transcript will be sent. 
| sendConversation | True | Used to filter which conversations are to be processed for sending.

Phone attribute can leverage the System's information about the user. 
*email* attributes require an additional step to validate user with either Amazon Connect Customer Profiles or a CRM integration.
*sendConversation* can be either set manually at the start of the conversation or asked by a prompt at some point of the conversation.

8. Create an Amazon Connect rule from the Amazon Connect Management interface. The rule requires the following definitions.

### Conditions.
When: A Contact Lens post-call analysis is available.
If: Contact attribute **sendConversation** = True.

### Define Actions.
Assigned category: TranscriptSendingQueued
Additional action: Generate an Eventbridge event. Set action name as **SendConversation**.

## Configure Amazon Pinpoint
1. From the Amazon Pinpoint console, got to SMS and voice -> Phone numbers. Select the phone number to be used for receiving messages. Expand the Two-way SMS section and click **Enable two-way SMS** 
1. In the Incoming messages destination, select **Create a new SNS topic** enter a name for the SNS Topic and save the configuration. Make a note on the Topic name.

## Configure Lambda functions
### immediateSender function
1. From the AWS Lambda console, browse to Applications and then select the application deployed by SAM (connect-stenographer if you used the same name as shown in this instructions). Select the immediateSender function and browse to Configuration -> Environment variables. Fill the following information:

| key   | Value 
|----------|:-------------:
| PINPOINT_NUMBER |  Pinpoint assigned number for sending SMS messages.
| SOURCE_EMAIL | Verified SES email address for sending emails to users. This will be the email origin.

### messageTriggeredSender function
1. From the AWS Lambda console, browse to Applications and then select the application deployed by SAM (connect-stenographer if you used the same name as shown in this instructions). Select the messageTriggeredSender function and browse to Configuration -> Environment variables. Fill the following information:

| key   | Value 
|----------|:-------------:
| SOURCE_EMAIL | Verified SES email address for sending emails to users. This will be the email origin.

Important: Do not change the rest of the variables, as they have been pre set by the deployment template.

1. In the function configuration, click on **Add Trigger**, Select SNS and select the topic created while configuring the Pinpoint number. **Click Add** to save the configuration.


## Resource deletion
1. Delete the SNS topic created.
1. From the cloudformation console, select the stack associated with the application and click on Delete and confirm it by pressing Delete Stack. 

