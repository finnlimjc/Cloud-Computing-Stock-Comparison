# AWS Secrets Manager IAM Role

This IAM role lets the dashboard's EC2 instance read the Alpaca API key and secret key from **AWS Secrets Manager**, which is used to fetch news from Alpaca. With the role attached, the instance receives short-lived credentials automatically, so no access keys or `secrets.env` file need to be stored on it. The trusted entity is an AWS service, with EC2 as both the service and the use case. For permissions it uses the existing AWS managed policy `AWSSecretsManagerClientReadOnlyAccess`, which can read secrets but cannot create, change or delete them.

| Setting | Value |
|---|---|
| Role name | `alpaca-news-secrets-reader-role` |
| Description | Allows the stock dashboard EC2 instance to read the Alpaca API key and secret key from AWS Secrets Manager for fetching news. |

> **Disclaimer:** This setup was designed but not built, because IAM roles cannot be created in the AWS sandbox used for this project, and Secrets Manager is disabled for secret creation.

# AWS Systems Manager

Because Secrets Manager is disabled in the sandbox, the Alpaca keys are stored as encrypted `SecureString` parameters in **AWS Systems Manager Parameter Store** instead. The sandbox role only allows `ssm:*` on parameters under `/work/`, so both names must start with `/work/`. 

There is no CloudFormation template for these parameters, because CloudFormation cannot create `SecureString` parameters. Create them in the console instead: go to **Systems Manager → Parameter Store → Create parameter**, and create one parameter for each key with these settings:

| Setting | API key | Secret key |
|---|---|---|
| Name | `/work/alpaca-api-key` | `/work/alpaca-secret-key` |
| Description | Alpaca API Key | Alpaca Secret Key |
| Tier | Standard | Standard |
| Type | SecureString | SecureString |
| Data type | text | text |
| KMS key source | My current account | My current account |
| KMS Key ID | `alias/aws/ssm` | `alias/aws/ssm` |
| Value | Your Alpaca API key | Your Alpaca secret key |

Then check that both were saved by reading them back decrypted in CloudShell:
```
aws ssm get-parameters --names /work/alpaca-api-key /work/alpaca-secret-key --with-decryption
```

The output should list both parameters under `Parameters`, each with its decrypted `Value`. Any name that could not be found appears under `InvalidParameters`.

The web servers read these parameters through the existing `EC2InstanceRole` (see [aws-ec2-iam-role.md](aws-ec2-iam-role.md)), whose policy allows `ssm:*` on `/work/*`.
