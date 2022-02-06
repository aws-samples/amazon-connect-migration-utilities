# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Known Issues:
#   Contact flows and modules can not have an apostrophe -- ie GetUserInput and PlayPrompt.
#   describe_contact_flow and describe_contact_flow_module will error both in boto3 and from the CLI
#
#   Lex V2 references must be manually mapped

import boto3
import re
import os
import sys
import json
from functools import reduce
import pydash as _

with open(os.path.join(sys.path[0], 'config.json'), "r") as file:
    config = json.load(file)

with open(os.path.join(sys.path[0], config["Output"]["ManifestFileName"]), "r") as file:
    output_arns = json.load(file)

template = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": config["Output"]["TemplateDescription"],
    "Resources": {}
}

phone_number_mappings = config["Input"]["PhoneNumberMappings"] if "PhoneNumberMappings" in config["Input"] else {}

client = boto3.client('connect')

# retrieve acount and instance specific arn parts for later substition with CF pseudo paramterers
sts_client = boto3.client("sts")
identity = sts_client.get_caller_identity()
account_number = identity["Account"]
connect_client = boto3.client('connect')
connect_arn = connect_client.describe_instance(InstanceId=config["Input"]["ConnectInstanceId"])["Instance"]["Arn"]
region = connect_arn.split(":")[3]
partition = connect_arn.split(":")[1]

# initialize id -> CF resource name mappings
contact_flows = {}
contact_flow_modules = {}
hours_of_operations = {}
quick_connects = {}


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
            properties["InstanceArn"] = {"Ref": "ConnectInstanceArn"}
            resource_name = re.sub(r'[\W_]+', '', contact_flow["Name"])
            contact_flows[contact_flow["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})

            # List of properties included in the API response that should not be mapped in the template
            excluded_properties = ["Id", "Arn", "ResponseMetadata", "InstanceId", "Tags", "Description"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]

            print(resource_name)
            content = replace_pseudo_parms(content)
            content = replace_with_mappings(content)

            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}


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
            properties["InstanceArn"] = {"Ref": "ConnectInstanceArn"}

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

            content = replace_pseudo_parms(content)
            content = replace_with_mappings(content)
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

            for source_phone, target_phone in phone_number_mappings.items():
                content = content.replace(source_phone, target_phone)
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

            # The API returns the state as lowercase.  CF requires it to be uppercase.
            state = template["Resources"][resource_name]["Properties"]["State"].upper()
            template["Resources"][resource_name]["Properties"]["State"] = state


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

            properties["InstanceArn"] = {"Ref": "ConnectInstanceArn"}
            resource_name = re.sub(r'[\W_]+', '', hours_of_operation["Name"])+"HoursOfOperation"
            hours_of_operations[hours_of_operation["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})
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

            properties["InstanceArn"] = {"Ref": "ConnectInstanceArn"}
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


def replace_contact_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        transfers = list(filter(lambda t: t["Type"] == "TransferToFlow", content["Actions"]))
        for transfer in transfers:
            contact_flow_arn = transfer["Parameters"]["ContactFlowId"]
            contact_flow_id = transfer["Parameters"]["ContactFlowId"].split("/")[-1]

            new_arn = contact_flow_arn.replace(contact_flow_id, "${" + contact_flows[contact_flow_id] + ".ContactFlowArn}")
            arn_replaced_content = \
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = arn_replaced_content
        modules = list(filter(lambda t: t["Type"] == "UpdateContactEventHooks", content["Actions"]))

        for module in modules:
            contact_flow_id = module["Parameters"]["EventHooks"]["CustomerQueue"].split("/")[-1]
            contact_flow_arn = module["Parameters"]["EventHooks"]["CustomerQueue"]
            new_arn = "${" + contact_flows[contact_flow_id] + ".ContactFlowArn}"

            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = \
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)


def replace_contact_module_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        modules = list(filter(lambda t: t["Type"] == "InvokeFlowModule", content["Actions"]))
        for module in modules:
            contact_flow_id = module["Parameters"]["FlowModuleId"]
            new_arn = "${" + contact_flow_modules[contact_flow_id] + "}"
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = \
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_id, new_arn)


def replace_hours_of_operation():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
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

            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] =\
                template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(hours_arn, new_arn)


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
                breakpoint()

    return content


def replace_with_mappings_queue(content, action):
    if "queue" in action:
        print(action)
        text = _.get(action, "text")
        queue_id = _.get(action, "id")
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


for name in config["ResourceFilters"]["ContactFlows"]:
    # export_quick_connects(name,"AWS::Connect::QuickConnect")
    export_hours_of_operation(name, "AWS::Connect::HoursOfOperation")
    export_contact_flow(name, "AWS::Connect::ContactFlow")
    export_contact_flow_modules(name, "AWS::Connect::ContactFlowModule")

replace_contact_flowids()
replace_contact_module_flowids()
replace_hours_of_operation()


template["Parameters"] = {
    "ConnectInstanceID": {
        "Type": "String",
        "AllowedPattern": ".+",
        "ConstraintDescription": "ConnectInstanceID is required"
    },
    "ConnectInstanceArn": {
        "Type": "String",
        "AllowedPattern": ".+",
        "ConstraintDescription": "ConnectInstanceArn is required"
    }
}

with open(os.path.join(sys.path[0], config["Output"]["Filename"]), 'w') as f:
    json.dump(template, f, indent=4, default=str)
