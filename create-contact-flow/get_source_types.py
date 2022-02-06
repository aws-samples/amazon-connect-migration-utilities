import boto3
import re
import os
import sys
import json
import pydash
from functools import reduce

mapping={}

with open(os.path.join(sys.path[0], 'config.json'), "r") as file:
    config = json.load(file)

client = boto3.client('connect')

def get_types():
    paginator = client.get_paginator('list_contact_flow_modules')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   ContactFlowModuleState="Active",
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["ContactFlowModulesSummaryList"] = {}
        for module in page["ContactFlowModulesSummaryList"]:
            mapping["ContactFlowModulesSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":module["Id"]
            }

    paginator = client.get_paginator('list_contact_flows')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
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
        mapping["ContactFlowSummaryList"] = {}
        for module in page["ContactFlowSummaryList"]:
            print(module)
            mapping["ContactFlowSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":module["Id"]
            }
            
    paginator = client.get_paginator('list_hours_of_operations')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["HoursOfOperationSummaryList"]={}
        for module in page["HoursOfOperationSummaryList"]:
            mapping["HoursOfOperationSummaryList"][module["Name"]] = module["Arn"]
    
    paginator = client.get_paginator('list_phone_numbers')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   PhoneNumberTypes=["TOLL_FREE","DID"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["PhoneNumberSummaryList"]={}
        for module in page["PhoneNumberSummaryList"]:
            mapping["PhoneNumberSummaryList"][module["PhoneNumber"]] = {
                "Arn":module["Arn"],
                "Name":module["PhoneNumber"]
            }

    paginator = client.get_paginator('list_prompts')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["PromptSummaryList"] = {}
        for module in page["PromptSummaryList"]:
            mapping["PromptSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":module["Id"]
            }

    paginator = client.get_paginator('list_queues')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   QueueTypes = ["STANDARD","AGENT"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["QueueSummaryList"] ={}
        for module in page["QueueSummaryList"]:
            if "Name" not in module:
                continue
            mapping["QueueSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":pydash.get(module,"Id")
            }
    paginator = client.get_paginator('list_quick_connects')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   QuickConnectTypes = ["USER","QUEUE","PHONE_NUMBER"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["QuickConnectSummaryList"] = {}
        for module in page["QuickConnectSummaryList"]:
            mapping["QuickConnectSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":module["Id"]
            }

    paginator = client.get_paginator('list_routing_profiles')
    for page in paginator.paginate(InstanceId=config["Output"]["ConnectInstanceId"],
                                   PaginationConfig={
                                                     "MaxItems": 50,
                                                     "PageSize": 50,
                                    }):
        mapping["RoutingProfileSummaryList"] ={}
        for module in page["RoutingProfileSummaryList"]:
            mapping["RoutingProfileSummaryList"][module["Name"]] = {
                "Arn":module["Arn"],
                "Id":module["Id"]
            }

get_types()
with open(os.path.join(sys.path[0], config["Output"]["ManifestFileName"]), 'w') as f:
    json.dump(mapping, f, indent=4, default=str)