# Amazon Connect Migration Utilities

## Background

Amazon Connect is an omnichannel cloud contact center that helps companies provide superior customer service at a lower cost. Amazon Connect provides a seamless experience across voice and chat for customers and agents. This includes one set of tools for skills-based routing, powerful real-time and historical analytics, and easy-to-use intuitive management tools – all with pay-as-you-go pricing.

An Amazon Connect contact flow defines the customer experience with your contact center from start to finish, including setting logging behavior, setting text-to-speech language and voice, capturing customer inputs (spoken or by pressing 0-9 on the phone keypad), playing prompts, and transferring to appropriate queue. 

While the contact flow builder’s graphical user interface in Amazon Connect allows contact center managers to easily create dynamic, personal, and automated customer experiences without needing to write a single line of code, once the contact flows are created, there is not a straight forward method to migrate the contact flows you created among Connect Instances.

The *Amazon Connect Migration Utilities* contains Python scripts that allow you to easily migrate Amazon Connect contact flows between Connect Instances.

## Requirements

- [Python 3.7](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

## Install the prerequisite CloudFormation custom resources

CloudFormation custom resources enable you to write custom provisioning logic in templates that AWS CloudFormation runs anytime you create, update (if you changed the custom resource), or delete stacks. 

The ```create-contact-flow-template.py``` script leverages custom resources to attach Lambdas to your 
Amazon Connect instance.

### Deploying the custom resources

From the command line, run the following commands. This will deploy AWS Lambda custom resources that can be called by your CloudFormation template.

```bash
sam build -t cfn-contact-flow-custom-resources.yml --use-container
sam deploy  --template-file .aws-sam/build/template.yaml --stack-name cfn-contact-flow-custom-resources   --capabilities "CAPABILITY_NAMED_IAM" --resolve-s3
```

## Usage

There are two Python scripts included in the project:

- ```create-source-manifest-file.py``` - creates a file containing names and ids of resources in the **source** instance of Connect such as defaut queues, audio prompts, and routing profiles along with any existing contact flows in the source account.
   The resulting ```source-manifest.json``` file is used to map ids between the destination account and the source account.
- ```create-contact-flow-template.py```- creates an AWS CloudFormation template that you can use to import contact flows to a destination Connect instance.


### Create a manifest file from the source account

***TODO: Support ```--profile``` command line argument and add explanation about how to use Cloudshell as an alternative***

When you create an Amazon Connect instance, it comes with default contact flows, queues, prompts and other resources.  The identifiers of those resources are unique per instance and are referenced in the contact flows when exported from Connect.

The ```create-contact-flow-template``` script needs to know how to map the identifiers between the source Connect instance and the destination instance.

The ```create-source-manifest-file``` script exports the identifiers from the *source* Connect instance to a _manifest_ file that ```create-contact-flow-template``` uses for its mappings.

First create a ```config.json``` file in the root project directory.

```json
{
    "Output": {
        "ConnectInstanceId": "2f1b6bff-73f7-4c20-965d-aa833d7eddfd",
        "ManifestFileName":"source-manifest.json"
    }
}
```

| Field                        | Description                                                       |
|------------------------------|-------------------------------------------------------------------|
| Output -> ConnectInstanceId  |  the ID of the *destination* Connect instance                     |
| Output -> ManifestFileName   |  the filename that ```create-source-manifest-file``` will create. |

and then run the create-source-manifest-file from the account with the *source* Connect instance.

*Note: The script currently does not support the ```--region``` option.  Set your region by running the following command from the command line.

```
export AWS_DEFAULT_REGION=<YOUR REGION>
```


```bash
python3 create-source-manifest-file.py
```

### Export the Connect contact flows to a CloudFormation template

Now that you have the manifest file containing the source Connect instance's resource identifiers, you can create the CloudFormation template.

First add the following items to the config.json file.

```bash
{
    "Input": {
        "ConnectInstanceId": "<source connect instance ID>,
        "PhoneNumberMappings": {
            "+15551234567": "+15557654321",
            "+15556767671": "+16664351235"
        }
    },
    "ResourceFilters": {
        "ContactFlows": [
            "migration-sample"
        ]
    },
    "Output": {
        "Filename": "contact-flows.json",
        "TemplateDescription": "Connect Contact Flows",
        "ConnectInstanceId": "2f1b6bff-73f7-4c20-965d-aa833d7eddfd",
        "ManifestFileName":"source-manifest.json"
    }
}
```

| Field                                 | Description                                                                      |
|---------------------------------------|----------------------------------------------------------------------------------|
| Input->ConnectInstanceId              |  the ID of the Connect instance containing the contact flows you want to export  |
| Input->PhoneNumberMappings            | (optional) the exporter will replace the phone number on the left with the phone number on the right.The phone number must exist in the destination account |
| Input->ResourceFilters->ContactFlows  | The exporter will export any *published* contact flows where the name contains one of the listed words |
| Output->Filename                      | The name of the output CloudFormation template. |
| Output->TemplateDescription           |  Describes the purpose of the stack. |

Then run the script:

```bash
pip3 install -r requirements.txt #First time only
python3 create-contact-flow-template.py
```

Once you run the script, a CloudFormation template will be created that you can deploy either via the AWS console or via the AWS CLI.

**TODO: Add walkthrough with screenshots**

The template requires one parameter, ConnectInstanceId, which should be the instance where you want to create your contact flows.

## Supported Amazon Connect Types


| Resource             | Level of support                          |
|----------------------|-------------------------------------------|
| Contact flows        | exports and mappings                      |
| Contact flow modules | exports and mappings                      |
| Hours of operations  | exports                                   |
| AWS Lambda           | mappings and permissions                  |
| Amazon Lex           | mappings and permissions                  |
| Audio prompts        | mapping                                   |
| Queues               | mapping                                   |
| Phone numbers        | mapping                                   |



Definitions:

- exports - the script is able to read from a source Connect instance and export the definition in the CloudFormation template
- mappings - the script is able to read from a manifest file created by ```create-source-manifest-file.py``` and map
  the resource to the corresponding source resource.
- permissions - Permission is added to the Connect instance. But it has to already exist.
  
## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.