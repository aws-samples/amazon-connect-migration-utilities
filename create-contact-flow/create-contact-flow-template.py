# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Known Issues:
#   Contact flows and modules can not have an apostrophe -- ie GetUserInput and PlayPrompt. 
#   describe_contact_flow and describe_contact_flow_module will error both in boto3 and from the CLI
import boto3
import re
import os
import sys
import json
from functools import reduce

with open(os.path.join(sys.path[0], 'config.json'), "r") as file:
    config = json.load(file)
template = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": config["Output"]["TemplateDescription"],
    "Resources": {}
}

phone_number_mappings = config["Input"]["PhoneNumberMappings"] if "PhoneNumberMappings" in config["Input"] else {}

client = boto3.client('connect')

sts_client = boto3.client("sts")
account_number = sts_client.get_caller_identity()["Account"]


contact_flows = {}
contact_flow_modules = {}
hours_of_operations = {}


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
            properties["InstanceArn"] = {"Ref": "ConnectInstanceID"}
            resource_name = re.sub(r'[\W_]+', '', contact_flow["Name"])
            contact_flows[contact_flow["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})
            excluded_properties = ["Id", "Arn", "ResponseMetadata","InstanceId"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]
            content = content.replace(account_number, "${AWS::AccountId}")
            for source_phone, target_phone in phone_number_mappings.items():
                content = content.replace(source_phone,target_phone)
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content }           
            content = content.replace(config["Input"]["ConnectInstanceId"], "${ConnectInstanceID}")
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}
            template["Resources"][resource_name]["Properties"]["Name"] = {"Fn::Sub":template["Resources"][resource_name]["Properties"]["Name"] + "${ResourceSuffix}"}


def export_contact_flow_modules(name, resource_type):
    paginator = client.get_paginator('list_contact_flow_modules')
    for page in paginator.paginate(InstanceId=config["Input"]["ConnectInstanceId"],
                                   ContactFlowModuleState = "active",
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):

        for contact_flow_module in page["ContactFlowModulesSummaryList"]:
            if(name not in contact_flow_module["Name"]):
                continue
            
            print(contact_flow_module["Id"].split("/")[-1])
            print(config["Input"]["ConnectInstanceId"])
            properties = client.describe_contact_flow_module(
                InstanceId=config["Input"]["ConnectInstanceId"],
                ContactFlowModuleId=contact_flow_module["Id"].split("/")[-1]
            )

            properties = properties["ContactFlowModule"]


            properties["InstanceArn"] = {"Ref": "ConnectInstanceID"}
            resource_name = re.sub(r'[\W_]+', '', contact_flow_module["Name"])+"Module"
            contact_flow_modules[contact_flow_module["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})
            excluded_properties = ["Id", "Arn", "ResponseMetadata","InstanceId","Status"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]
            content = content.replace(account_number, "${AWS::AccountId}")
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content }           
            content = content.replace(config["Input"]["ConnectInstanceId"], "${ConnectInstanceID}")
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}
            template["Resources"][resource_name]["Properties"]["Name"] = {"Fn::Sub":template["Resources"][resource_name]["Properties"]["Name"] + "${ResourceSuffix}"}
            print("here")
            breakpoint()

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
            
            print(config["Input"]["ConnectInstanceId"])
            properties = client.describe_hours_of_operation(
                InstanceId=config["Input"]["ConnectInstanceId"],
                HoursOfOperationId=hours_of_operation["Id"].split("/")[-1]
            )["HoursOfOperation"]


            properties["InstanceArn"] = {"Ref": "ConnectInstanceID"}
            resource_name = re.sub(r'[\W_]+', '', hours_of_operation["Name"])+"HoursOfOperation"
            hours_of_operations[hours_of_operation["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                    }
                }})
            excluded_properties = ["Id", "Arn", "ResponseMetadata","InstanceId","HoursOfOperationId","HoursOfOperationArn"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            template["Resources"][resource_name]["Properties"]["Name"] = {"Fn::Sub":template["Resources"][resource_name]["Properties"]["Name"] + "${ResourceSuffix}"}



def replace_contact_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        transfers = list(filter(lambda t: t["Type"] == "TransferToFlow", content["Actions"]))
        for transfer in transfers:
            contact_flow_arn = transfer["Parameters"]["ContactFlowId"]
            contact_flow_id = transfer["Parameters"]["ContactFlowId"].split("/")[-1]
            new_arn = contact_flow_arn.replace(contact_flow_id, "${" + contact_flows[contact_flow_id] + ".ContactFlowId}")
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)

def replace_contact_module_flowids():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        modules = list(filter(lambda t: t["Type"] == "InvokeFlowModule", content["Actions"]))
        for module in modules:
            contact_flow_id = module["Parameters"]["FlowModuleId"]
            new_arn =  "${" + contact_flow_modules[contact_flow_id] + "}"
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_id, new_arn)

def replace_hours_of_operation():
    for resource in template["Resources"]:
        if "Content" not in template["Resources"][resource]["Properties"]:
            continue
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        check_hours = list(filter(lambda t: t["Type"] == "CheckHoursOfOperation", content["Actions"]))
        for hours in check_hours:
            
            #Hours is optional in CheckHoursOfOperations. 
            #If it is not specified. Hours attached to the current queue are checked.

            if "Hours" not in hours["Parameters"]:
                continue

            hours_arn = hours["Parameters"]["Hours"]
            hours_id = hours_arn.split("/")[-1]
            new_arn =  "arn:${AWS::Partition}:connect:${AWS::Region}:${AWS::AccountId}:instance/${ConnectInstanceID}/operating-hours/${"+hours_of_operations[hours_id]+".HoursOfOperationArn}"
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(hours_arn, new_arn)



for name in config["ResourceFilters"]["ContactFlows"]:
    export_hours_of_operation(name,"AWS::Connect::HoursOfOperation")
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
    "ResourceSuffix": {
        "Type": "String",
        "Default": "",
        "Description": "Optional suffix to add each resource"
    }
}

with open(os.path.join(sys.path[0], config["Output"]["Filename"]), 'w') as f:
    json.dump(template, f, indent=4, default=str)
