// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
var AWS = require("aws-sdk");
var CfnLambda = require("cfn-lambda");
var response = require("cfn-response");

var Connect = new AWS.Connect();

// CloudFormation sends everything as a String, have to coerce these values.
const boolProperties = [];

// CloudFormation sends everything as a String, have to coerce these values.
const numProperties = [];

// Simple PUT operation. The returned attributes are only important ones for
//   other resources to know about.

const Create = CfnLambda.SDKAlias({
  api: Connect,
  forceNums: numProperties,
  forceBools: boolProperties,
  method: "createContactFlow",
  returnPhysicalId: "ContactFlowId",
  returnAttrs: ["ContactFlowId", "ContactFlowArn"],
});

const Update = CfnLambda.SDKAlias({
  api: Connect,
  forceNums: numProperties,
  forceBools: boolProperties,
  method: "updateContactFlowContent",
  returnPhysicalId: "ContactFlowId",
  physicalIdAs: "ContactFlowId",
  returnAttrs: ["ContactFlowId", "ContactFlowArn"],
});

exports.handler = CfnLambda(
  {
    Create: Create,
    Update: Update,
    // Contact Flows can't be deleted
    Delete: (RequestPhysicalID, CfnRequestParams, reply) => {
      let connect = new AWS.Connect()
      console.log("Deleting....")
      connect.describeContactFlow({
        ContactFlowId: RequestPhysicalID,
        InstanceId: CfnRequestParams.InstanceId
      }).promise()
        .then(data => connect.updateContactFlowName({
          ContactFlowId: RequestPhysicalID,
          InstanceId: CfnRequestParams.InstanceId,
          Description: "Renamed by CloudFormation",
          Name: "ZZZZ_DELETED_" + data.ContactFlow.Name + Math.random().toString(36).replace(/[^a-z]+/g, '').substr(0, 5)
        }).promise())
        .then(() => reply(null, RequestPhysicalID))
        .catch(e => {
          console.log(e)
          reply(e, RequestPhysicalID)}
        )
    }
  })
