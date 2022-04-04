# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Known Issues:
#   Contact flows and modules can not have an apostrophe -- ie GetUserInput and PlayPrompt.
#   describe_contact_flow and describe_contact_flow_module will error both in boto3 and from the CLI
#
#   Lex V2 references must be manually attached to the Connect instance
#  
#   Lambdas must be manually attached to the Connect instance

import boto3
import re
import os
import sys
import json
from functools import reduce
import pydash as _

# config.json contains the configuration information needed by the rest of the script
with open(os.path.join(sys.path[0], 'config.json'), "r") as file:
    config = json.load(file)

# The manifest file contains mappings of resources and their identifiers from the source
# Amazon Connect instance.  This file is created by the create-source-manifest-file.py script

with open(os.path.join(sys.path[0], config["Output"]["ManifestFileName"]), "r") as file:
    output_arns = json.load(file)

template = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": config["Output"]["TemplateDescription"],
    "Resources": {}
}

# contains mappings to tell the script how to replace phone numbers found in the destination instance with
# phone numbers found in the source instance.  
phone_number_mappings = config["Input"]["PhoneNumberMappings"] if "PhoneNumberMappings" in config["Input"] else {}

client = boto3.client('connect')

# The ARNs for Connect resources contain account specific information. ie:
# arn:aws:connect:us-east-1:987654321:contact_flow/...
#
# The script replaces the account specific parts with their CloudFormation psuedo parameter equivalents.
# arn:${AWS::Partition}:connect:${AWS::Region}:${AWS::AccountId}:contact_flow/...

# Get the current account number
sts_client = boto3.client("sts")
identity = sts_client.get_caller_identity()
account_number = identity["Account"]

#Get the current region
connect_client = boto3.client('connect')
connect_arn = connect_client.describe_instance(InstanceId=config["Input"]["ConnectInstanceId"])["Instance"]["Arn"]
region = connect_arn.split(":")[3]


# Parse the current partition
# For standard AWS Regions, the partition is aws. 
# For resources in other partitions, the partition is aws-partitionname. 
# For example, the partition for resources in the China (Beijing and Ningxia) Region is aws-cn 
# and the partition for resources in the AWS GovCloud (US-West) region is aws-us-gov.

partition = connect_arn.split(":")[1]

# initialize id -> CF resource name mappings
contact_flows = {}
contact_flow_modules = {}
hours_of_operations = {}
quick_connects = {}

# Uses the Connect APIs to retrieve contact flows from the Connect instance
# the format of the exported contact flows is not the same as what are exported from
def export_contact_flow(name, resource_type):
    paginator = client.get_paginator('list_contact_flows')
    for page in paginator.paginate(InstanceId=config["Input"]["ConnectInstanceId"],
                                   ContactFlowTypes=['CONTACT_FLOW',
                                                     'CUSTOMER_QUEUE',
                                                     'CUSTOMER_HOLD',
                                                     'CUSTOMER_WHISPER',
                                                     'AGENT_HOLD',
                                                     'AGENT_WHISPER',
                                                     'OUTBOUND_WHISPER',
                                                     'AGENT_TRANSFER',
                                                     'QUEUE_TRANSFER'],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):

        # we only want to retrieve contact flows specified in the config file
        for contact_flow in page["ContactFlowSummaryList"]:
            if(name not in contact_flow["Name"]):
                continue
            try:
                properties = client.describe_contact_flow(
                    InstanceId=config["Input"]["ConnectInstanceId"],
                    ContactFlowId=contact_flow["Id"]
                )["ContactFlow"]
            except client.exceptions.ContactFlowNotPublishedException:
                print(f"Warning: {contact_flow['Name']} is not published, Unable to export.")
                continue
            properties["InstanceArn"] = {"Fn::Sub": connect_arn}
            
            #Make sure the CloudFormation logical resource name is valud
            resource_name = re.sub(r'[\W_]+', '', contact_flow["Name"])
            contact_flows[contact_flow["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})

            # Some properties  that are returned by the API call should not be included in the output template
            excluded_properties = ["Id", "Arn", "ResponseMetadata", "InstanceId", "Tags", "Description"]
            keys_to_add = list(properties.keys() - set(excluded_properties))
            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))

            # add the contact flow to the the CF template
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]

            print(resource_name)
            # Replace the hard coded partition, region, account number and Connect Instance ID with parameters
            content = replace_pseudo_parms(content)

            # some resource types are created by default when you create a Connect instance
            # the identifiers will be different between accounts.  Map the source identifiers to the destination
            content = replace_with_mappings(content)
            print(json.dumps(json.loads(content),indent=2))

            # Add the resource to the template
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

# Uses the Connect APIs to retrieve contact flow modules from the Connect instance
# the format of the exported contact flows is not the same as what are exported from Connect
def export_contact_flow_modules(name, resource_type):
    paginator = client.get_paginator('list_contact_flow_modules')
    for page in paginator.paginate(InstanceId=config["Input"]["ConnectInstanceId"],
                                   ContactFlowModuleState="active",
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):

        for contact_flow_module in page["ContactFlowModulesSummaryList"]:
            if(name not in contact_flow_module["Name"]):
                continue

            properties = client.describe_contact_flow_module(
                InstanceId=config["Input"]["ConnectInstanceId"],
                ContactFlowModuleId=contact_flow_module["Id"].split("/")[-1]
            )

            properties = properties["ContactFlowModule"]
            properties["InstanceArn"] = {"Fn::Sub": connect_arn}

            # CF ResourceNames should only contain letters and a '-'
            resource_name = re.sub(r'[\W_]+', '', contact_flow_module["Name"])+"Module"
            contact_flow_modules[contact_flow_module["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})

            # Map API response to CF properties and exclude properties that are not supported.
            excluded_properties = ["Id", "Arn", "ResponseMetadata", "InstanceId", "Status", "Tags", "Description"]
            keys_to_add = list(properties.keys() - set(excluded_properties))
            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))

            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]

            # Replace the hard coded partition, region, account number and Connect Instance ID with parameters
            content = replace_pseudo_parms(content)

            # some resource types are created by default when you create a Connect instance
            # the identifiers will be different between accounts.  Map the source identifiers to the destination
            content = replace_with_mappings(content)
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

            # Map the phone number from the destination Connect instance to the source connect instance
            for source_phone, target_phone in phone_number_mappings.items():
                content = content.replace(source_phone, target_phone)
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

            # The API returns the state as lowercase.  CF requires it to be uppercase.
            state = template["Resources"][resource_name]["Properties"]["State"].upper()
            template["Resources"][resource_name]["Properties"]["State"] = state

# Uses the Connect APIs to retrieve hours of operations from the Connect instance
# the format of the exported contact flows is not the same as what are exported from
def export_hours_of_operation(name, resource_type):
    paginator = client.get_paginator('list_hours_of_operations')
    for page in paginator.paginate(InstanceId=config["Input"]["ConnectInstanceId"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):

        for hours_of_operation in page["HoursOfOperationSummaryList"]:
            if(name not in hours_of_operation["Name"]):
                continue

            properties = client.describe_hours_of_operation(
                InstanceId=config["Input"]["ConnectInstanceId"],
                HoursOfOperationId=hours_of_operation["Id"].split("/")[-1]
            )["HoursOfOperation"]

            properties["InstanceArn"] = {"Fn::Sub": connect_arn}

            # CF ResourceNames should only contain letters and a '-'
            resource_name = re.sub(r'[\W_]+', '', hours_of_operation["Name"])+"HoursOfOperation"
            hours_of_operations[hours_of_operation["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})

            # Map API response to CF properties and exclude properties that are not supported.
            excluded_properties = [
                "Id",
                "Arn",
                "ResponseMetadata",
                "InstanceId",
                "HoursOfOperationId",
                "HoursOfOperationArn",
                "Tags",
                "Description"
            ]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))

# Uses the Connect APIs to retrieve quick connects from the Connect instance
# the format of the exported contact flows is not the same as what are exported from
def export_quick_connects(name, resource_type):
    paginator = client.get_paginator('list_quick_connects')
    for page in paginator.paginate(InstanceId=config["Input"]["ConnectInstanceId"],
                                   QuickConnectTypes=["USER", "QUEUE", "PHONE_NUMBER"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):

        for quick_connect in page["QuickConnectSummaryList"]:
            if(name not in quick_connect["Name"]):
                continue

            properties = client.describe_quick_connect(
                InstanceId=config["Input"]["ConnectInstanceId"],
                QuickConnectId=quick_connect["Id"].split("/")[-1]
            )["QuickConnect"]

            properties["InstanceArn"] = {"Fn::Sub": connect_arn}
            resource_name = re.sub(r'[\W_]+', '', quick_connect["Name"])+"QuickConnect"
            quick_connects[quick_connect["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})
            excluded_properties = ["Id",
                                   "Arn",
                                   "ResponseMetadata",
                                   "InstanceId",
                                   "QuickConnectId",
                                   "QuickConnectARN",
                                   "Tags",
                                   "Description"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))


# By the time this method is called, the original arn that is contained in the exported contact flow
# has been converted from this:
#
# arn:aws:connect:us-east-1:987654321:instance/aaaaaa-bbbb-cc1c-dddd-123456789abc/flowid/a1a2a3-dddd-a1b1-dddd-123456789abc
# 
# to this
#
# arn:${AWS::Partition}:connect:${AWS::Region}:${AWS::AccountId}:flowid/instance/${ConnectInstandId}/flowid/a1a2a3-dddd-a1b1-dddd-123456789abc
# 
# Now we need to replace the resource identifier GUIDs with the contact flow ARNs of the newly created resources
# using the CloudFormation !Ref and !GetAtt intrinsic functions
#
# arn:${AWS::Partition}:connect:${AWS::Region}:${AWS::AccountId}:flowid/instance/${ConnectInstandId}/flowid/${SampleFlow.ContactFlowArn}
# 
# the CloudFormation resource names to identifiers mapping was created while the ContactFlows were being
# exported.
def replace_contact_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])

        # Transfer to agent actions can reference contact flows
        transfers = list(filter(lambda t: t["Type"] == "TransferToFlow", content["Actions"]))
        for transfer in transfers:
            contact_flow_arn = transfer["Parameters"]["ContactFlowId"]
            contact_flow_id = transfer["Parameters"]["ContactFlowId"].split("/")[-1]

            new_arn = contact_flow_arn.replace(contact_flow_id, "${" + contact_flows[contact_flow_id] + ".ContactFlowArn}")
            arn_replaced_content = \
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = arn_replaced_content

        # As can UpdateContactEventHooks...
        modules = list(filter(lambda t: t["Type"] == "UpdateContactEventHooks", content["Actions"]))
        for module in modules:
            contact_flow_id = module["Parameters"]["EventHooks"]["CustomerQueue"].split("/")[-1]
            contact_flow_arn = module["Parameters"]["EventHooks"]["CustomerQueue"]
            new_arn = "${" + contact_flows[contact_flow_id] + ".ContactFlowArn}"

            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = \
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)

# Returns the contact flow identifier in the destination instance based on the manifest file
# by the identifier referenced in the source contact flow
# 
# This allows contact flows to reference pre-existing contact flows in the destination Connect instance
# that are not being exported
def get_dest_contact_flow_module(contact_flow_id):
    # first look in the current Connect instance
    contact_flow = client.describe_contact_flow_module(
                InstanceId=config["Input"]["ConnectInstanceId"],
                ContactFlowModuleId=contact_flow_id
            )
    contact_flow_name = contact_flow["ContactFlowModule"]["Name"]
    id = _.get(output_arns,["ContactFlowModulesSummaryList",contact_flow_name,"Id"])
    return {
        "name":contact_flow_name,
        "id":id
    }

    
# This is the same concept as replace_contact_flowids() for contact flow modules
def replace_contact_module_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        content_string = template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"]
        modules = list(filter(lambda t: t["Type"] == "InvokeFlowModule", content["Actions"]))
        cf_vars = {}
        for module in modules:
            contact_flow_id = module["Parameters"]["FlowModuleId"]
            
            dest_module = get_dest_contact_flow_module(contact_flow_id)
            name = dest_module["name"]
            if(contact_flow_id not in contact_flow_modules):
                if(dest_module["id"] is None):
                    raise Exception(
                        f"The referenced module ${dest_module['name']} " +
                        f"in the contact flow ${resource} was not exported and not found in " +
                        f"in the destination Connect instance")
                new_arn = dest_module["id"]
            else:
                new_arn = "${" + contact_flow_modules[contact_flow_id] + "}"
 


            content_string  = content_string.replace(contact_flow_id, new_arn)

        template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"]= [content_string,cf_vars]

# This is the same concept as replace_contact_flowids() for contact flow modules
def replace_hours_of_operation():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"][0])
        check_hours = list(filter(lambda t: t["Type"] == "CheckHoursOfOperation", content["Actions"]))
        for hours in check_hours:
            # Hours is optional in CheckHoursOfOperations.
            # If it is not specified. Hours attached to the current queue are checked.
            if "Hours" not in hours["Parameters"]:
                continue

            hours_arn = hours["Parameters"]["Hours"]
            hours_id = hours_arn.split("/")[-1]
            new_arn =\
                "arn:${AWS::Partition}:connect:${AWS::Region}:" +\
                "${AWS::AccountId}:instance/${ConnectInstanceID}/operating-hours/${" + \
                hours_of_operations[hours_id]+".HoursOfOperationArn}"

            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"][0] =\
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"][0].replace(hours_arn, new_arn)


# There are default audio prompts and queues that come with a Connect instance
# map the identifiers to the destination Connect instance
def replace_with_mappings(content):
    content = replace_with_config_mappings(content)
    contact_flow = json.loads(content)
    metadata = _.get(contact_flow, "Metadata.ActionMetadata", {})
    for flow_command in metadata:
        action = metadata[flow_command]
        content = replace_with_mappings_audio_prompt(content, action)
        content = replace_with_mappings_queue(content, action)
    return content


def replace_with_config_mappings(content):
    for source_phone, target_phone in phone_number_mappings.items():
        content = content.replace(source_phone, target_phone)
    return content


def replace_with_mappings_audio_prompt(content, action):
    if "audio" in action:
        for audio in action["audio"]:
            if(_.get(audio, "type") == "Prompt"):
                text = _.get(audio, "text")
                source_id = _.get(audio, "id").split("/")[-1]
                dest_id = _.get(output_arns, ["PromptSummaryList", text, "Id"])
                content = content.replace(source_id, dest_id)
                print(json.dumps(json.loads(content), indent=2))

    return content


def replace_with_mappings_queue(content, action):
    if "queue" in action:
        print(action)
        text = _.get(action, "queue.text")
        queue_id = _.get(action, "queue.id")
        if(queue_id is not None):
            source_id = queue_id.split("/")[-1]
            dest_id = _.get(output_arns, ["QueueSummaryList", text, "Id"])
            content = content.replace(source_id, dest_id)

    return content


def replace_pseudo_parms(content):
    content = content.replace(account_number, "${AWS::AccountId}")
    content = content.replace(partition, "${AWS::Partition}")
    content = content.replace(region, "${AWS::Region}")
    content = content.replace(config["Input"]["ConnectInstanceId"], "${ConnectInstanceID}")
    return content


# Currently, the script exporting:
#   - hours of operation
#   - contact flow
#   - contact flow modules


connect_arn = replace_pseudo_parms(connect_arn)

for name in config["ResourceFilters"]["ContactFlows"]:
    # export_quick_connects(name,"AWS::Connect::QuickConnect")
    export_hours_of_operation(name, "AWS::Connect::HoursOfOperation")
    export_contact_flow(name, "AWS::Connect::ContactFlow")
    export_contact_flow_modules(name, "AWS::Connect::ContactFlowModule")


replace_contact_flowids()
replace_contact_module_flowids()
replace_hours_of_operation()


# Add the parameters section to the CloudFormation template
template["Parameters"] = {
    "ConnectInstanceID": {
        "Type": "String",
        "AllowedPattern": ".+",
        "ConstraintDescription": "ConnectInstanceID is required"
    }
}

with open(os.path.join(sys.path[0], config["Output"]["Filename"]), 'w') as f:
    json.dump(template, f, indent=4, default=str)

print(connect_arn)
