# AWS RDS Database

> **Source:** [scripts/04-stock-research-database.yaml](../scripts/04-stock-research-database.yaml) (CloudFormation).

> **Disclaimer:** Sandbox settings have restrictions on certain settings, which are all documented in this markdown.

## Overview

The dashboard stores users and document metadata (see [database-tables.md](database-tables.md)) in an Amazon RDS for PostgreSQL instance. It sits in the VPC's two private subnets (see [aws-vpc-architecture.md](aws-vpc-architecture.md)), has no public IP, and only accepts connections from the web servers. The file contents live in the [S3 bucket](aws-s3-bucket.md).

| Setting | Value |
|---|---|
| DB instance identifier | `stock-research-db` |
| Engine | PostgreSQL 18.3 |
| Creation method | Full configuration |
| Template | Dev/Test |
| Deployment | Single-AZ DB instance (1 instance) |
| Instance class | `db.t3.micro` (Burstable, 2 vCPUs, 1 GiB RAM) |
| Storage | 20 GiB General Purpose SSD (`gp2`), autoscaling up to 100 GiB |
| Initial database name | `stockresearch` |
| Port | `5432` |
| Public access | No |
| Deletion policy | Snapshot |

## Deployment order

Deploy this stack after [scripts/03-stock-research-dashboard-vpc.yaml](../scripts/03-stock-research-dashboard-vpc.yaml), because it needs the VPC, the private subnets and the Web Security Group. Pick them from the dropdowns when creating the stack:

| Parameter | Choose |
|---|---|
| `VpcId` | `stock-research-dashboard-vpc` |
| `PrivateSubnet1Id` | `stock-research-dashboard-subnet-private1-us-east-1a` (`10.0.1.0/24`) |
| `PrivateSubnet2Id` | `stock-research-dashboard-subnet-private2-us-east-1b` (`10.0.3.0/24`) |
| `WebSecurityGroupId` | `Web Security Group` |
| `ParameterPrefix` | Leave the default `/work/stock-research` |

Inside the stack, the DB instance references the DB subnet group and the DB security group, so CloudFormation creates both of them first and the instance next. The host name parameter references the instance, so it is created after it.

## Sandbox restrictions

The sandbox limits RDS to Aurora, MySQL, PostgreSQL and MariaDB; nano, micro, small and medium On-Demand instances; `gp2` storage up to 100 GB; no Multi-AZ; and no Enhanced Monitoring. These settings differ from the intended console setup:

| Setting | Intended | Sandbox (template) | Reason |
|---|---|---|---|
| Deployment | Multi-AZ DB instance (primary + standby in another AZ) | Single-AZ | Multi-AZ is not supported. |
| Storage type | `gp3` | `gp2` | Only `gp2` is supported. |
| Maximum storage threshold | 1000 GiB | 100 GiB | Storage is capped at 100 GB. |
| Credentials management | Managed in AWS Secrets Manager | Self managed (`main` / `lab-password`) | Secrets Manager is disabled in the sandbox (see [aws-secrets-manager.md](aws-secrets-manager.md)). |
| Enhanced Monitoring | Off | Off | Not supported; it must stay unchecked. |

**Production:** use Multi-AZ so a standby in the other AZ takes over if the primary fails, `gp3` storage, and let RDS manage the master password in Secrets Manager.

## Credentials

| Setting | Value |
|---|---|
| Master username | `main` (`DBMasterUsername` parameter) |
| Master password | `lab-password` (`DBMasterPassword` parameter, `NoEcho`) |
| Credentials management | Self managed |
| Database authentication | Password authentication |

These are test credentials for the sandbox only, so they are documented here and set as parameter defaults. The dashboard reads the username from `/work/stock-research/db-username`, which this stack writes from `DBMasterUsername`, and the password from `/work/stock-research/db-password`, which is created by hand because CloudFormation cannot create SecureStrings (see [aws-secrets-manager.md](aws-secrets-manager.md#dashboard-parameters)). That password must equal `DBMasterPassword`.

## Instance class

### Why burstable classes

The dashboard is an internal tool with a few users. Its load is long quiet stretches (nobody logged in, overnight, weekends) and short spikes (someone logs in, saves an analysis or opens **Previous Analyses**). Each request is a small indexed query on small tables, so the database is idle almost all the time.

## Storage

| Setting | Value |
|---|---|
| Storage type | General Purpose SSD (`gp2`) |
| Allocated storage | 20 GiB (the minimum) |
| Storage autoscaling | Enabled |
| Maximum storage threshold | 100 GiB (sandbox cap) |
| Encryption | Enabled, AWS managed key `aws/rds` |

The database holds only metadata, so 20 GiB is far more than it needs today. Autoscaling grows the volume automatically if free space runs low, up to 100 GiB, so it never fills up unattended Encryption cannot be turned on after the instance is created, so it is enabled now; the default `aws/rds` key costs nothing extra.

## Connectivity

| Setting | Value |
|---|---|
| Compute resource | Don't connect to an EC2 compute resource (access is set up through the security group instead) |
| VPC | `stock-research-dashboard-vpc` |
| DB subnet group | `stock-research-subnet-group` |
| Public access | No |
| VPC security group | `DB Security Group` |
| RDS Proxy | Not created (extra cost; a few users do not need connection pooling) |
| Port | `5432` |

### DB subnet group

| Setting | Value |
|---|---|
| Name | `stock-research-subnet-group` |
| Description | Stock research dashboard subnet group. |
| VPC | `stock-research-dashboard-vpc` |
| Subnets | `stock-research-dashboard-subnet-private1-us-east-1a` (`10.0.1.0/24`), `stock-research-dashboard-subnet-private2-us-east-1b` (`10.0.3.0/24`) |

Only the private subnets are used, so the database has no route to or from the internet. RDS requires a subnet group to cover at least two Availability Zones even for a Single-AZ instance, which also lets the instance move to Multi-AZ in production without changing the subnet group.

### DB Security Group

| Direction | Protocol | Port | Source | Description |
|---|---|---|---|---|
| Inbound | TCP | 5432 (PostgreSQL) | `Web Security Group` | Permit PostgreSQL from web servers |
| Outbound | All | All | `0.0.0.0/0` | AWS default |

The source is the Web Security Group itself, not an IP range. Any instance in that group (both web servers, and any future ones) can connect, the rule keeps working when their IPs change, and nothing else can reach the database.

## Connecting from the dashboard

The web servers find and log in to the database through Parameter Store:

| Setting | Source |
|---|---|
| Host, username | `/work/stock-research/db-host` and `/work/stock-research/db-username`, written by this stack (see [Parameters for the dashboard](#parameters-for-the-dashboard)) |
| Password | `/work/stock-research/db-password`, created by hand |
| Port, database name | `5432` and `stockresearch`, constants in `src/dashboard/config.py` |

- `postgres_url` in `src/storage/database.py` builds the SQLAlchemy URL `postgresql+psycopg://...?sslmode=require`. `psycopg` is the PostgreSQL driver in `requirements.txt`. RDS for PostgreSQL 18 rejects unencrypted connections by default (`rds.force_ssl = 1`), so SSL is required explicitly.
- The engine uses `pool_pre_ping`, so a connection that RDS has closed while the dashboard sat idle is replaced instead of failing the next query.
- The tables are created by the dashboard on its first start (`metadata.create_all`), and existing tables are left alone. The schema is described in [database-tables.md](database-tables.md).
- Only the Web Security Group can reach port 5432, so the database cannot be opened from a laptop or CloudShell outside the VPC.

### Parameters for the dashboard

The stack writes the dashboard's non-secret settings to Parameter Store (`AWS::SSM::Parameter`, type String), under the `ParameterPrefix` parameter (default `/work/stock-research`, the same as `SSM_PREFIX` in `src/dashboard/config.py`):

| Resource | Parameter | Value |
|---|---|---|
| `BucketNameParameter` | `<prefix>/bucket-name` | `stock-research-bucket-${AWS::AccountId}-${AWS::Region}`, built the same way as in [01-stock-research-s3-bucket.yaml](../scripts/01-stock-research-s3-bucket.yaml) |
| `DBHostParameter` | `<prefix>/db-host` | `StockResearchDB.Endpoint.Address`. The endpoint (for example `stock-research-db.abcdefghijkl.us-east-1.rds.amazonaws.com`) contains an ID that RDS assigns when the instance is created, so it is written after the instance exists. |
| `DBUsernameParameter` | `<prefix>/db-username` | The `DBMasterUsername` parameter |

CloudFormation can only create String parameters, not SecureStrings, so `db-password` is still created by hand.

- Do not create these three parameters by hand, or the stack fails with "already exists".
- Deleting the stack deletes them. The web servers then show a "Missing parameters" error until the stack is created again.

## Additional configuration

| Setting | Value |
|---|---|
| DB parameter group | `default.postgres18` |
| Option group | `default:postgres-18` |
| Automated backups | Enabled, 7 days retention, no preferred window |
| Copy tags to snapshots | On |
| Backup replication to another Region | Off |
| Auto minor version upgrade | On |
| Maintenance window | No preference |
| Deletion protection | Off |

## Deletion policy

The instance uses `DeletionPolicy: Snapshot` and `UpdateReplacePolicy: Snapshot`. Deleting or replacing the stack takes a final snapshot first, so the users and document metadata can be restored. The snapshot is kept (and billed) until it is deleted manually. Deletion protection is off so the sandbox stack can be torn down; turn it on in production.

## Tags

| Key | Value |
|---|---|
| Name | `stock-research-db` |
| Project | `stock-research-dashboard` (`ProjectName` parameter) |
| Environment | `Prod` (`Environment` parameter) |
| Team | `DevOps` (`Team` parameter) |
| DataClassification | `private` (password hashes and which stocks are researched) |
| CostCenter | Same as Project (`ProjectName` parameter) |

The DB subnet group and DB Security Group carry only a `Name` tag, like the networking resources in the VPC stack.

## Outputs

| Output | Description |
|---|---|
| `DBEndpointAddress` | Host name of the database. |
| `DBEndpointPort` | PostgreSQL port (`5432`). |
| `DBName` | Initial database name (`stockresearch`). |
| `DBSecurityGroupId` | ID of the DB Security Group. |
| `BucketNameParameterName` | SSM parameter holding the bucket name (`/work/stock-research/bucket-name`). |
| `DBHostParameterName` | SSM parameter holding the host name (`/work/stock-research/db-host`). |
| `DBUsernameParameterName` | SSM parameter holding the username (`/work/stock-research/db-username`). |
