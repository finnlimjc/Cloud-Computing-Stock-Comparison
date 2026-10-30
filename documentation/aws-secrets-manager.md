# AWS Secrets Manager IAM Role

This IAM role lets the dashboard's EC2 instance read the Alpaca API key and secret key from **AWS Secrets Manager**, which is used to fetch news from Alpaca. With the role attached, the instance receives short-lived credentials automatically, so no access keys or `secrets.env` file need to be stored on it. The trusted entity is an AWS service, with EC2 as both the service and the use case. For permissions it uses the existing AWS managed policy `AWSSecretsManagerClientReadOnlyAccess`, which can read secrets but cannot create, change or delete them.

| Setting | Value |
|---|---|
| Role name | `alpaca-news-secrets-reader-role` |
| Description | Allows the stock dashboard EC2 instance to read the Alpaca API key and secret key from AWS Secrets Manager for fetching news. |

> **Disclaimer:** This setup was designed but not built, because IAM roles cannot be created in the AWS sandbox used for this project, and Secrets Manager is disabled for secret creation.

# AWS Systems Manager

Because Secrets Manager is disabled in the sandbox, the Alpaca keys are stored as encrypted `SecureString` parameters in **AWS Systems Manager Parameter Store** instead. The sandbox role only allows `ssm:*` on parameters under `/work/`, so both names must start with `/work/`. 

Open the AWS CLI and run the two commands below to store the keys, replacing the placeholder values with your own Alpaca API key and secret key:
```
aws ssm put-parameter --name /work/alpaca-api-key --value "<ALPACA_API_KEY>" --type SecureString
aws ssm put-parameter --name /work/alpaca-secret-key --value "<ALPACA_SECRET_KEY>" --type SecureString
```

Then check that both were saved by reading them back decrypted:
```
aws ssm get-parameters --names /work/alpaca-api-key /work/alpaca-secret-key --with-decryption
```

The output should list both parameters under `Parameters`, each with its decrypted `Value`. Any name that could not be found appears under `InvalidParameters`.

The web servers read these parameters through the existing `EC2InstanceRole` (see [aws-ec2-iam-role.md](aws-ec2-iam-role.md)), whose policy allows `ssm:*` on `/work/*`.
