process.env.AWS_SDK_LOAD_CONFIG = true;
const AWS = require("aws-sdk");
const response = require("cfn-response-async");
const connect = new AWS.Connect();

exports.handler = async function(event, context) {
  try {
    console.log(JSON.stringify(event, null, 2));
    var instanceId = event.ResourceProperties.InstanceId;
    var aliasArn = event.ResourceProperties.AliasArn;
    if (!instanceId || !aliasArn) {
      throw "InstanceId and aliasArn are required.";
    }

    var params = {
      InstanceId: instanceId,
      LexV2Bot: {
        AliasArn: aliasArn,
      },

    };

    if (event.RequestType == "Delete") {
      await connect
        .disassociateBot({
          InstanceId: instanceId,
          LexV2Bot: {
            AliasArn: aliasArn
          }
        })
        .promise();
    }
    if (event.RequestType == "Update" || event.RequestType == "Create") {
      await connect.associateBot(params).promise();
    }
    await response.send(event, context, "SUCCESS", {});
  }
  catch (e) {
    console.log(e);
    await response.send(event, context, "FAILED", {});
  }
};
