CFNConnectAssociateLambda is a custom resource used to associate a Lambda to a Connect instance.

```yaml
  GetContactLambdaPermission:
    Type: Custom::ConnecctAssociateLambda
    Properties:
      InstanceId: !Ref ConnectInstanceID
      FunctionArn: !GetAtt SampleLambda.Arn 
      ServiceToken: !ImportValue CFNConnectAssociateLambda
```