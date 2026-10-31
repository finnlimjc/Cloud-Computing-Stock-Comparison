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

The web servers read these parameters through the existing `EC2InstanceRole` (see [aws-ec2-iam-role.md](aws-ec2-iam-role.md)), whose policy allows `ssm:*` on `/work/*`. If they are missing, news falls back to Yahoo Finance.

## Dashboard parameters

The dashboard also reads its storage settings from Parameter Store when it starts, through `ParameterStore` in `src/storage/parameters.py`. Create these before deploying the stacks, in the same place (**Systems Manager → Parameter Store → Create parameter**, Standard tier, Data type `text`):

| Name | Type | Value | Description |
|---|---|---|---|
| `/work/stock-research/bucket-name` | String | `stock-research-bucket-<account-id>-us-east-1` | Bucket from [01-stock-research-s3-bucket.yaml](../scripts/01-stock-research-s3-bucket.yaml). The name is fixed by the account ID and Region, so it can be created before the stack. |
| `/work/stock-research/db-username` | String | `main` | RDS master username, the `DBMasterUsername` parameter of stack 04. |
| `/work/stock-research/db-password` | SecureString (`alias/aws/ssm`) | `lab-password` | RDS master password. It must equal the `DBMasterPassword` parameter of stack 04. |

Two more kinds of parameter are created for you. **Do not create them by hand:**

| Name | Type | Created by | Description |
|---|---|---|---|
| `/work/stock-research/db-host` | String | Stack 04 (`DBHostParameter`) | RDS endpoint address. It only exists once RDS has created the instance, so the stack writes it. CloudFormation can create String parameters but not SecureStrings, and the host name is not secret. If it already exists, stack 04 fails with "already exists". |
| `/work/stock-research/seed/<username>` | SecureString | The dashboard | Generated password of each [demo account](../README.md#demo-accounts-and-the-admin) (`admin`, `alice`, `bob`, `carol`), written with `ssm:PutParameter` the first time the account is created. |

Check them in CloudShell:
```
aws ssm get-parameters --names /work/stock-research/bucket-name /work/stock-research/db-host /work/stock-research/db-username /work/stock-research/db-password --with-decryption
aws ssm get-parameter --name /work/stock-research/seed/admin --with-decryption
```

The database port (`5432`) and name (`stockresearch`) do not change between environments, so they are constants in `src/dashboard/config.py` rather than parameters. If a parameter is missing, the dashboard shows "Could not open storage: Missing parameters in Parameter Store: ..." with the names, and connects on the next page refresh once they exist.
