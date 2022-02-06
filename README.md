# Amazon Connect Migration Utilities

## Purpose

This project contains an [AWS CloudFormation](https://aws.amazon.com/cloudformation/) [custom resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-custom-resources.html) that manages [Amazon Connect](https://aws.amazon.com/connect/) contact flows.
and a Python script that exports existing contact flows from Connect into a CloudFormation template that references the custom resource.

## Requirements

- The [AWS CLI](https://www.python.org/downloads/)
- The [AWS Serverless Application Model](https://docs.aws.amazon.com/serverless-application-model/index.html) must be [installed](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
- [Python 3.7](https://www.python.org/downloads/)
- [Node 12.x](https://nodejs.org/en/download/)

## CFNCreateContactFlow Custom Resource

CloudFormation does not natively support creating an Amazon Connect contact flow.  CFNCreateContactFlow is a custom resource that enables you to create and update contact flows using CloudFormation.

Connect does not support deleting contact flows.  

## CFNLambdaConnectPermission Custom Resource

CloudFormation does not natively support attaching a Lambda to Amazon Connect.  CFNLambdaConnectPermission is a custom resource that enables you to use CloudFormation to attach a Lambda to
a Connect instance.

Connect does not support deleting contact flows.  

### Deploying the custom resources

From the command line, run the following commands. This will deploy an AWS Lambda custom resource that can be called by your CloudFormation template.

```bash
sam build -t cfn-contact-flow-custom-resources.yml
sam deploy  --template-file .aws-sam/build/template.yaml --stack-name cfn-contact-flow-custom-resources   --capabilities "CAPABILITY_NAMED_IAM" --resolve-s3
```

### Using the CFNCreateContactFlow custom resource

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Connect Contact Flows
Resources:
  sample:
    Type: Custom::ConnectContactFlow
    Properties:
      ServiceToken: !ImportValue: CFNCreateContactFlow
      Description: A sample contact flow
      Content: '{stringified JSON content}'
      Type: CONTACT_FLOW
      Tags: {}
      InstanceId:
        Ref: ConnectInstanceID
      Name: sample
```

**Note**: The custom resource supports the contact flow format returned from the [describe-contact-flow](https://docs.aws.amazon.com/cli/latest/reference/connect/describe-contact-flow.html) [AWS CLI](https://aws.amazon.com/cli/) or the various [SDK's](https://aws.amazon.com/tools/).  This format is different from the one
that is exported from the web console.  

You can use the script described below to export a CloudFormation template from an existing Connect Instance.

## Contact Flow Exporter script

If you have items in a source Connect instance  that you want to import into a destination  Connect Instance,
you can use the *create-contact-flow-template* Python script.

### Usage

First create a config.json file in the create contact flow directory:

```json
{
    "Input":{
        "ConnectInstanceId":"<Your connect instance ID>",
        "PhoneNumberMappings":
        {
            "+15551234567":"+15557654321",
            "+15556767671":"+16664351235"
        }
    },
    "ResourceFilters":
    {
        "ContactFlows":["test1","test2"] 
    },
    "Output":{
        "Filename": "contact-flows.json",
        "TemplateDescription":"Connect Contact Flows"
    }
}
```
| Field  |Description   |
|---|---|
| ConnectInstanceId  |  the ID of the Connect instance containing your contact flows |
| PhoneNumberMappings | (optional) the exporter will replace the phone number on the left with the phone number on the right.The phone number must exist in the destination account |
|ContactFlows | The exporter will export any *published* contact flows where the name contains one of the listed words |
| Filename | The name of the output CloudFormation template. |
| TemplateDescription |  Describes the purpose of the stack. |

Then run the script:

```bash
cd create-contact-flow    
pip3 install -r requirements.txt #First time only
python3 create-contact-flow-template.py
```

Once you run the script, a CloudFormation template will be created.  

The template requires one parameter, ConnectInstanceId, which should be the instance where you want to create your contact flows.

### Features

- Replaces the source account number with the ${AWS::AccountId}
- Replaces the source Connect Instance Id with ${ConnectInstanceID}
- Allows you to map source phone number references to phone numbers in the destination.
- Replaces references in TransferToFlow to the correct destination references
- Connect does not allow you to delete a contact flow.  When a stack is deleted, CFNCreateContactFlow renames the contact flow to ZZZZ_Deleted_{contact flow name} and appends 8 random letters to the end.


### Using the CFNConnectAssociateLambda custom resource

CFNConnectAssociateLambda is a custom resource used to associate a Lambda to a Connect instance.

```yaml
  GetContactLambdaPermission:
    Type: Custom::ConnecctAssociateLambda
    Properties:
      InstanceId: !Ref ConnectInstanceID
      FunctionArn: !GetAtt SampleLambda.Arn 
      ServiceToken: !ImportValue CFNConnectAssociateLambda
```
## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.