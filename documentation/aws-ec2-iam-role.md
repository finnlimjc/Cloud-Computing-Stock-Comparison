# AWS EC2 IAM Role

> **Source:** [scripts/02-stock-research-ec2-role-policies.yaml](../scripts/02-stock-research-ec2-role-policies.yaml) (CloudFormation).

> **Disclaimer:** The sandbox does not allow creating or renaming IAM roles, only modifying existing ones. The template therefore adds inline policies to the existing `EC2InstanceRole` instead of creating its own role.

## Overview

The web servers need AWS permissions for two things: reading the Alpaca API keys and the dashboard's settings from SSM Parameter Store, and writing the demo account passwords there (see [aws-secrets-manager.md](aws-secrets-manager.md)); and saving, reading and deleting documents in the S3 bucket (see [aws-s3-bucket.md](aws-s3-bucket.md)). The database needs no IAM permission, because the dashboard logs in with a password and the DB Security Group controls network access. An IAM role attached through an instance profile gives the instances short-lived credentials automatically, so no access keys or `secrets.env` file are stored on them.

| Setting | Value |
|---|---|
| Role | `EC2InstanceRole` (existing, not managed by CloudFormation) |
| Instance profile | `Work-Role` (named differently from the role) |
| Inline policies added | `alpaca-ssm-parameters`, `notes-bucket-access` |

The template uses `AWS::IAM::RolePolicy`, which only needs `iam:PutRolePolicy` on the role. The role itself is never created, changed or deleted by the stack: deleting the stack only removes the two inline policies.

## Permissions

### `alpaca-ssm-parameters`

| Action | Resource |
|---|---|
| `ssm:*` | `arn:aws:ssm:*:*:parameter/work/*` |

The Alpaca keys are stored as `SecureString` parameters under `/work/` (the only path the sandbox allows). They are encrypted with the AWS managed `aws/ssm` KMS key, whose key policy already lets any principal in the account decrypt through SSM, so no `kms:Decrypt` permission is needed.

The same statement covers the dashboard's other parameters (see [aws-secrets-manager.md](aws-secrets-manager.md#dashboard-parameters)):

- `ssm:GetParameters` reads the bucket name and the database host, username and password.
- `ssm:PutParameter` writes the demo accounts' generated passwords to `/work/stock-research/seed/<username>`. Encrypting with `aws/ssm` needs no extra KMS permission either.

### `notes-bucket-access`

| Sid | Actions | Resource |
|---|---|---|
| `NotesObjectAccess` | `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:GetObjectVersion`, `s3:DeleteObjectVersion` | `arn:aws:s3:::stock-research-bucket-<account-id>-<region>/users/*` |
| `ListNotesBucket` | `s3:ListBucket` | `arn:aws:s3:::stock-research-bucket-<account-id>-<region>` |

- Object actions are limited to the `users/` folder (the `ObjectKeyPrefix` parameter), so the dashboard cannot touch anything else in the bucket. It matches the object key layout `users/{owner_id}/{document_id}/{filename}` in the README.
- `s3:ListBucket` applies to the bucket itself, not its objects, so it needs the bucket ARN without `/*`. Without it, reading a missing file returns `403 Access Denied` instead of `404 Not Found`.
- The version actions are needed because the bucket is versioned: they let the app read or permanently remove a specific version.
- The bucket name is built the same way as in [01-stock-research-s3-bucket.yaml](../scripts/01-stock-research-s3-bucket.yaml), so it must stay in sync if that name changes.

## Attaching the role to the instances

An instance can only be given a role through an instance profile, and EC2 asks for the **instance profile name**, not the role name. The two can differ: `EC2InstanceRole`'s instance profile is `Work-Role` (shown as **Instance profile ARN** on the role's Summary panel in the IAM console). Passing the role name instead fails with `Invalid IAM Instance Profile name`. Check the profile name with:

```
aws iam list-instance-profiles-for-role --role-name EC2InstanceRole
```

The load balancer template's `InstanceProfileName` parameter defaults to `Work-Role`. It is set in the launch template, so every instance the Auto Scaling group launches gets that instance profile.

1. Create the S3 bucket stack (`01-stock-research-s3-bucket.yaml`).
2. Create the policy stack (`02-stock-research-ec2-role-policies.yaml`). Tick the IAM acknowledgment checkbox (CLI: `--capabilities CAPABILITY_IAM`).
3. Create the VPC and database stacks (`03` and `04`).
4. Create the load balancer stack (`05-stock-research-load-balancer.yaml`). `InstanceProfileName` is already `Work-Role` by default.

## Sandbox vs production

| Area | Sandbox (now) | Production |
|---|---|---|
| Role | Existing `EC2InstanceRole`, shared with anything else that uses it | A dedicated role and instance profile created by the template, so the dashboard's permissions are not mixed with other workloads |
| Secrets store | SSM Parameter Store | AWS Secrets Manager with `secretsmanager:GetSecretValue` on the Alpaca secret |
