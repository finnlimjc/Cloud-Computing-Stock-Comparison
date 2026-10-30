# AWS VPC Architecture

![alt text](../assets/stock-research-dashboard-vpc.png)
> **Source:** [scripts/01-stock-research-dashboard-vpc.yaml](../scripts/01-stock-research-dashboard-vpc.yaml) (CloudFormation).

> **Disclaimer:** Sandbox settings have restrictions on certain settings, which are all documented in this markdown.

## Overview

The stock research dashboard (a Streamlit app) runs in its own VPC, spread across two Availability Zones for robustness. Users reach the dashboard through the public address of the web servers, and upload their PDF notes to Amazon S3.

| Setting | Value |
|---|---|
| Name tag prefix | `stock-research-dashboard` |
| Region | `us-east-1` (sandbox) |
| VPC CIDR | `10.0.0.0/16` (65,536 IPs) |
| Availability Zones | 2 (`us-east-1a`, `us-east-1b`) |
| DNS support / hostnames | Both enabled (instances get a public DNS name) |

## Region

| Environment | Region | Reason |
|---|---|---|
| Sandbox | `us-east-1` (N. Virginia) | The sandbox only permits this Region. |
| Production | `ap-southeast-1` (Singapore) | Which stocks the company researches is sensitive, and hosting data abroad may raise compliance issues. Keep data in Singapore. |

The template uses `!GetAZs` and `${AWS::Region}`, so moving to Singapore needs no change except the AMI ID (AMI IDs are Region-specific) and the AZ suffix in the Name tags.

## Network layout

| Subnet | Name tag | AZ | CIDR | Route table |
|---|---|---|---|---|
| Public 1 | `stock-research-dashboard-subnet-public1-us-east-1a` | us-east-1a | `10.0.0.0/24` | Public |
| Private 1 | `stock-research-dashboard-subnet-private1-us-east-1a` | us-east-1a | `10.0.1.0/24` | Private |
| Public 2 | `stock-research-dashboard-subnet-public2-us-east-1b` | us-east-1b | `10.0.2.0/24` | Public |
| Private 2 | `stock-research-dashboard-subnet-private2-us-east-1b` | us-east-1b | `10.0.3.0/24` | Private |

A subnet is "public" or "private" because of its route table, not the subnet itself. Public subnets also auto-assign a public IPv4 address to instances on launch.

### Gateways and endpoints

| Resource | Name tag | Purpose |
|---|---|---|
| Internet Gateway | `stock-research-dashboard-igw` | Connects the VPC to the internet. Used by the public route table. |
| S3 Gateway Endpoint | `stock-research-dashboard-vpce-s3` | Private route to S3 for the PDF notes users upload. Traffic stays on the AWS network and the endpoint itself is free. Attached to both route tables. |

### Route tables

| Route table | Destination | Target | Associated subnets |
|---|---|---|---|
| `stock-research-dashboard-rtb-public` | `10.0.0.0/16` | local | Public 1, Public 2 |
| | `0.0.0.0/0` | Internet Gateway | |
| | S3 prefix list | S3 Gateway Endpoint | |
| `stock-research-dashboard-rtb-private` | `10.0.0.0/16` | local | Private 1, Private 2 |
| | S3 prefix list | S3 Gateway Endpoint | |

### No NAT Gateway

A NAT Gateway is intentionally not deployed. Both web servers sit in public subnets with public IPs, so they reach the internet (`git clone`, `pip`, market-data APIs) through the Internet Gateway. The private subnets hold no workload and have no internet route, which keeps them unreachable from outside. This also avoids the NAT Gateway's hourly and per-GB charges.

## Security

### Web Security Group

| Direction | Protocol | Port | Source | Description |
|---|---|---|---|---|
| Inbound | TCP | 80 | `0.0.0.0/0` (Anywhere-IPv4) | Permit web requests |
| Inbound | TCP | 8501 | `0.0.0.0/0` (Anywhere-IPv4) | Permit Streamlit app |
| Outbound | All | All | `0.0.0.0/0` | AWS default |

- **No SSH (port 22) rule.** Users sign in through the dashboard by opening the public address, and nobody needs shell access to the servers.
- **HTTP is open to Anywhere-IPv4 in the sandbox** because the school's IP ranges are unknown. "My IP" would lock out students whose IP differs from the author's.
- **Production:** restrict ports 80/8501 to the company's IP ranges (or place the servers behind a load balancer and allow only that).
- Port 8501 is where Streamlit actually listens. Nothing listens on port 80 today; the rule is kept for a future reverse proxy or load balancer.

## Compute

Two identical EC2 instances, one in each public subnet, sharing the same Web Security Group. If one instance or AZ fails, the other keeps serving the dashboard.

| Setting | Value |
|---|---|
| Instances | `Web Server 1` (Public 1, us-east-1a) and `Web Server 2` (Public 2, us-east-1b) |
| Instance type | t2.micro |
| AMI | Amazon Linux 2023 |
| Storage | 8 GiB `gp3` |
| Network | Auto-assigned public IPv4 |
| Security group | Web Security Group |
| Key pair | None (no SSH access needed) |
| IAM instance profile | `EC2InstanceRole` (`InstanceProfileName` parameter). See [aws-ec2-iam-role.md](aws-ec2-iam-role.md). |
| Python | 3.11 (`python3.11` package) |
| App | Streamlit on `0.0.0.0:8501`|

### Bootstrap (user data)

On first boot each instance installs Git and Python 3.11 (the AMI's default `python3` is 3.9), clones the app from `github.com/finnlimjc/Cloud-Computing-Stock-Comparison` into `/opt/app`, installs `requirements.txt` into a Python 3.11 virtual environment, and starts the Streamlit service. Allow a few minutes after the stack finishes.

### Tags

Both instances carry the same tags; only `Name` differs.

| Key | Value |
|---|---|
| Name | `Web Server 1` / `Web Server 2` |
| Project | `stock-research-dashboard` (`ProjectName` parameter) |
| Environment | `Prod` (`Environment` parameter) |
| Team | `DevOps` (`Team` parameter) |
| CostCenter | Same as Project (`ProjectName` parameter) |

## Sandbox vs production

| Area | Sandbox (now) | Production |
|---|---|---|
| Region | `us-east-1` | `ap-southeast-1` |
| HTTP / Streamlit source | Anywhere-IPv4 | Company IP ranges only |
| Instance entry point | Two public IPs | Load balancer in front of both instances |
