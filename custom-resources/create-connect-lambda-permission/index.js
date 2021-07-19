
process.env.AWS_SDK_LOAD_CONFIG=true
const AWS = require("aws-sdk");
const response = require("cfn-response-async");
const connect = new AWS.Connect();

exports.handler = async function (event, context) {
  try {
    console.log("version " + AWS.VERSION)
    console.log(JSON.stringify(event, null, 2));
    var instanceId = event.ResourceProperties.InstanceId;
    var functionArn = event.ResourceProperties.FunctionArn;
    if (!instanceId && !functionArn) {
      throw "InstanceId,functonArn are required.";
    }
    var params = {
      FunctionArn: functionArn,
      InstanceId: instanceId,
    };

    if (event.RequestType == "Delete") {
      await connect.disassociateLambdaFunction(params).promise()
    }
    if (
      event.RequestType == "Update" ||
      event.RequestType == "Create"
    ) {
      await connect.associateLambdaFunction(params).promise()
    }
    await response.send(event, context, "SUCCESS", {});
  } catch (e) {
    console.log(e);
    await response.send(event, context, "FAILED", {});
  }
};



