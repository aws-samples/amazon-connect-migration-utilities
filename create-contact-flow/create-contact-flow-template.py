# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

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

client = boto3.client('connect')
paginator = client.get_paginator('list_contact_flows')

sts_client = boto3.client("sts")
account_number = sts_client.get_caller_identity()["Account"]


contact_flows = {}


def export_contact_flow(name, resource_type, service_token):
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
            print(properties["Content"])
            properties["InstanceId"] = {"Ref": "ConnectInstanceID"}
            resource_name = re.sub(r'[\W_]+', '', contact_flow["Name"])
            contact_flows[contact_flow["Id"]] = resource_name
            template["Resources"].update(
                {resource_name: {
                    "Type": resource_type,
                    "Properties": {
                        "ServiceToken": {"Fn::ImportValue": service_token}
                    }
                }})
            excluded_properties = ["Id", "Arn", "ResponseMetadata"]
            keys_to_add = list(properties.keys() - set(excluded_properties))

            properties_to_add = list(map(lambda x: {x: properties[x]}, keys_to_add))
            template["Resources"][resource_name]["Properties"].update(reduce(lambda a, b: dict(a, **b), properties_to_add))
            content = template["Resources"][resource_name]["Properties"]["Content"]
            content = content.replace(account_number, "${AWS::AccountId}")
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content }
            
            content = content.replace(config["Input"]["ConnectInstanceId"], "${ConnectInstanceID}")
            template["Resources"][resource_name]["Properties"]["Content"] = {"Fn::Sub": content}

            template["Resources"][resource_name]["Properties"]["InstanceId"] = {"Ref": "ConnectInstanceID"}
            template["Resources"][resource_name]["Properties"]["Name"] = {"Fn::Sub":template["Resources"][resource_name]["Properties"]["Name"] + "${ResourceSuffix}"}
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


def add_dependencies():
    for resource in template["Resources"]:
        content = json.loads(template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"])
        transfers = list(filter(lambda t: t["Type"] == "TransferToFlow", content["Actions"]))
        for transfer in transfers:
            contact_flow_arn = transfer["Parameters"]["ContactFlowId"]
            contact_flow_id = transfer["Parameters"]["ContactFlowId"].split("/")[-1]
            new_arn = contact_flow_arn.replace(contact_flow_id, "${" + contact_flows[contact_flow_id] + ".ContactFlowId}")
            template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"] = template["Resources"][resource]["Properties"]["Content"]["Fn::Sub"].replace(contact_flow_arn, new_arn)


for name in config["ResourceFilters"]["ContactFlows"]:
    export_contact_flow(name, "Custom::ConnectContactFlow", "CFNCreateContactFlow")
add_dependencies()


with open(os.path.join(sys.path[0], config["Output"]["Filename"]), 'w') as f:
    json.dump(template, f, indent=4, default=str)
