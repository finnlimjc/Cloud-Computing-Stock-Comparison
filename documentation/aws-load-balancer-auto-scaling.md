# AWS Load Balancer and Auto Scaling

> **Source:** [scripts/05-stock-research-load-balancer.yaml](../scripts/05-stock-research-load-balancer.yaml) (CloudFormation).

> **Disclaimer:** Sandbox settings have restrictions on certain settings, which are all documented in this markdown.

## Overview

An internet-facing Application Load Balancer (ALB) is the single public entry point to the dashboard. It spreads users across the two original web servers and an Auto Scaling group of 2 to 6 instances in the private subnets. Auto Scaling adds instances when the dashboard is busy and removes them when it is quiet, keeping the average CPU near 60%.

```text
User ── HTTP:80 ──> StockResearchELB (public subnets, both AZs)
                        │ forward, sticky cookie
                        v
                 StockResearchGroup (HTTP:8501)
                   ├── Web Server 1 / Web Server 2 (public subnets)
                   └── StockResearchAutoScalingGroup, 2 to 6 instances (private subnets)
                              │ outbound only (git, pip, market data, SSM)
                              v
                      NAT Gateway in the same AZ
```

| Resource | Name |
|---|---|
| Load balancer | `StockResearchELB` |
| Listener | HTTP:80 → `StockResearchGroup` |
| Target group | `StockResearchGroup` |
| Launch template | `StockResearchConfig` |
| Auto Scaling group | `StockResearchAutoScalingGroup` |
| Scaling policy | Target tracking, average CPU 60% |

## Deployment order

1. Create stacks `01` to `04` (see the [README](../README.md#aws)). Stack 03 must include the NAT Gateways, because the Auto Scaling instances install the app from the internet at first boot.
2. Delete any load balancer, target group, launch template or Auto Scaling group with the names above that was built by hand in the console. The names are fixed in the template, so the stack fails if they already exist.
3. Create stack `05` and pick:

   | Parameter | Value |
   |---|---|
   | `VpcId` | `stock-research-dashboard-vpc` |
   | `PublicSubnet1Id` / `PublicSubnet2Id` | `...-subnet-public1-us-east-1a` / `...-subnet-public2-us-east-1b` |
   | `PrivateSubnet1Id` / `PrivateSubnet2Id` | `...-subnet-private1-us-east-1a` / `...-subnet-private2-us-east-1b` |
   | `WebSecurityGroupId` | `Web Security Group` |
   | `WebServer1Id` / `WebServer2Id` | `Web Server 1` / `Web Server 2` |
   | `InstanceProfileName` | `Work-Role` (default) |

4. Open `LoadBalancerURL` from the stack's **Outputs** tab. The Auto Scaling group starts with no instances and launches 2. Each needs a few minutes to install the app before the target group marks it healthy. Until then, the ALB sends users to Web Server 1 and 2.

## Sandbox restrictions

| Restriction | Effect |
|---|---|
| Only Amazon-provided Linux and Windows AMIs can be launched | The launch template cannot use an AMI made from Web Server 1. Each instance starts from Amazon Linux 2023 (`ami-0fef201115eefe936`) and installs the app with the same user data as Web Server 1. |
| Roles cannot be created | The instances use the existing `Work-Role` instance profile (see [aws-ec2-iam-role.md](aws-ec2-iam-role.md)). |
| `us-east-1` only | The AMI ID is for `us-east-1` and must change for another Region. |

## Load balancer

| Setting | Value | Reason |
|---|---|---|
| Type | Application Load Balancer | The dashboard is HTTP. |
| Scheme | Internet-facing | Users connect from the internet. Needs public subnets. |
| IP address type | IPv4 | |
| Subnets | Public 1 (us-east-1a), Public 2 (us-east-1b) | One load balancer node per AZ, so it survives the loss of one AZ. |
| Security group | `Web Security Group` | Already allows HTTP (80) from anywhere. |
| Listener | HTTP:80, forward to `StockResearchGroup` (weight 1) | Users open the plain URL without a port. The ALB translates to Streamlit's 8501. |
| Cross-zone load balancing | On (always on for an ALB) | Targets in both AZs share the load evenly. |

## Target group

| Setting | Value |
|---|---|
| Target type | Instances |
| Protocol / port | HTTP / 8501 (Streamlit) |
| Protocol version | HTTP1 |
| VPC | `stock-research-dashboard-vpc` |
| Health check | HTTP `/`, default thresholds and interval |
| Registered targets | Web Server 1, Web Server 2, and every instance the Auto Scaling group launches |

### Stickiness

Stickiness is turned on with a load balancer generated cookie for 1 day. The dashboard needs it:

- Streamlit keeps each user's session in the memory of the server it connected to: the login (`st.session_state.user`) and the cached analysis results.
- File uploads (`/_stcore/upload_file/...`) and downloads and the PDF viewer (`/media/...`) are separate HTTP requests outside the WebSocket. They only work on the server that holds the session.

Without stickiness the ALB could send these requests to another instance, and uploads or downloads would fail at random. A user whose instance is removed by scale-in, or fails, is moved to another instance and has to log in again.

## Launch template

| Setting | Value |
|---|---|
| Name | `StockResearchConfig` |
| AMI | Amazon Linux 2023 (see [Sandbox restrictions](#sandbox-restrictions)) |
| Instance type | t2.micro |
| Key pair | None (no SSH access needed) |
| Subnet | Not set: Auto Scaling picks the subnet |
| Security group | `Web Security Group` |
| IAM instance profile | `Work-Role`, to read settings from SSM and documents from S3 |
| Detailed CloudWatch monitoring | Enabled: CPU metrics every minute instead of every 5, so scaling reacts faster (extra charge) |
| Storage | AMI default (8 GiB `gp3`) |
| User data | Same as Web Server 1: install Python 3.11, clone the app, install `requirements.txt`, run Streamlit on 8501 |

Each instance clones the repository when it launches, so newly launched instances run the latest code on GitHub, while older instances keep the code they started with. Push changes before scaling, or refresh the instances.

## Auto Scaling group

| Setting | Value |
|---|---|
| Name | `StockResearchAutoScalingGroup` |
| Launch template | `StockResearchConfig`, latest version |
| Subnets | Private 1 (us-east-1a), Private 2 (us-east-1b) |
| AZ distribution | Balanced best effort (default) |
| Load balancer | Attached to `StockResearchGroup` |
| Desired / minimum / maximum | 2 / 2 / 6 |
| Group metrics | Sent to CloudWatch every minute |
| Health check type | EC2 (default) |
| Notifications | None |

- **Private subnets:** the instances have no public IP and can only be reached through the load balancer. They reach the internet through the NAT Gateway in their AZ (see [aws-vpc-architecture.md](aws-vpc-architecture.md#nat-gateways)).
- **Minimum 2:** one instance per AZ at all times, so the dashboard keeps running if one AZ fails.
- **Maximum 6:** caps the cost of a traffic spike.

### Scaling policy

| Setting | Value |
|---|---|
| Policy type | Target tracking |
| Metric | Average CPU utilization of the group |
| Target value | 60% |

Auto Scaling adds instances when the group's average CPU stays above 60% and removes them when it stays well below. Building price, drawdown and company metrics for several tickers is CPU-heavy on a t2.micro, so CPU follows load closely. At 60% there is still headroom while a new instance takes a few minutes to install the app.

## Tags

Every resource carries the same tags as the other stacks; only `Name` differs. The Auto Scaling group copies its tags onto every instance it launches (`PropagateAtLaunch`).

| Key | Value |
|---|---|
| Name | `StockResearchELB` / `StockResearchGroup` / `StockResearchConfig` / `Stock Research Instance` (instances) |
| Project | `stock-research-dashboard` (`ProjectName` parameter) |
| Environment | `Prod` (`Environment` parameter) |
| Team | `DevOps` (`Team` parameter) |
| CostCenter | Same as Project (`ProjectName` parameter) |

The listener and the scaling policy have no tags.

## Outputs

| Output | Value |
|---|---|
| `LoadBalancerURL` | `http://<load balancer DNS name>`, the dashboard's public address |
| `TargetGroupArn` | ARN of `StockResearchGroup` |
| `AutoScalingGroupName` | `StockResearchAutoScalingGroup` |
