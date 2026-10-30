# AWS S3 Bucket

> **Source:** [scripts/01-stock-research-s3-bucket.yaml](../scripts/01-stock-research-s3-bucket.yaml) (CloudFormation).

## Overview

The dashboard stores the PDF notes users upload in a single private S3 bucket. The web servers reach it through the VPC's S3 Gateway Endpoint (see [aws-vpc-architecture.md](aws-vpc-architecture.md)), so the traffic stays on the AWS network.

| Setting | Value |
|---|---|
| Bucket name | `stock-research-bucket-${AWS::AccountId}-${AWS::Region}` |
| Region | `us-east-1` (sandbox) |
| Bucket type | General purpose |
| Bucket namespace | Global namespace |
| Block all public access | On (all four settings) |
| Bucket Versioning | Enabled |
| Default encryption | SSE-S3 (Amazon S3 managed keys) |
| Bucket Key | Disabled |
| Object Lock | Disabled |
| Lifecycle rule | `expire-old-versions` (whole bucket) |
| Deletion policy | Retain |

## Bucket name

Bucket names in the global namespace must be unique across every AWS account, and 3 to 63 characters long. Appending the account ID and Region makes the name unique and lets the same template deploy to the sandbox (`us-east-1`) and production (`ap-southeast-1`) without edits. For example: `stock-research-bucket-123456789012-us-east-1`.

## Bucket type

**General purpose** is used rather than **Directory**. Directory buckets only support S3 Express One Zone, which stores data in a single Availability Zone for low latency. The notes are small PDFs that do not need low latency, and general purpose buckets store objects across multiple Availability Zones, so the notes survive an AZ failure.

## Security

### Block Public Access

All four Block Public Access settings are on. Which stocks the company researches is sensitive, so no ACL or bucket policy should ever be able to expose the notes publicly. The dashboard accesses the bucket with its own AWS credentials, so it does not need public access.

### Default encryption

Every new object is encrypted with **SSE-S3** (AES-256, keys managed by S3). It has no extra cost and no key management. SSE-KMS and DSSE-KMS add per-request KMS charges and need KMS permissions, which the sandbox restricts. Bucket Key is disabled because it only reduces KMS calls and has no effect with SSE-S3.

## Versioning

Versioning keeps every version of an object. When a user deletes a file, S3 adds a *delete marker* instead of erasing the data, and an overwritten file keeps its previous version. This protects against accidental deletes and application bugs.

Because old versions are kept, they still use (and are billed for) storage. The [lifecycle rule](#lifecycle-rule) permanently removes them after 30 days.

## Lifecycle rule

One rule, `expire-old-versions`, applies to all objects in the bucket (no prefix or tag filter).

| Action | Setting | Reason |
|---|---|---|
| Permanently delete noncurrent versions | 30 days after becoming noncurrent | A deleted or overwritten note stays recoverable for 30 days, then is removed for good so storage does not grow forever. |
| Delete expired object delete markers | On | Once every old version of a deleted file has expired, only its delete marker remains. Removing it keeps listings clean and leaves nothing behind. |
| Delete incomplete multipart uploads | 7 days after initiation | A large upload that fails midway leaves hidden parts that are still billed. After 7 days they are deleted. |

Not used:

- **Transition current / noncurrent versions between storage classes** - the notes are small PDFs read on demand, so cheaper storage classes would save little and add retrieval fees and minimum storage durations.
- **Expire current versions** - this would delete files users still want. Users decide when their notes are deleted.

The 30 days is the trade-off between recovery window and storage cost. "Number of newer versions to retain" is left empty, so every noncurrent version expires after 30 days regardless of how many there are.

## Object Lock

Object Lock is **disabled**, because users must be able to delete the files they upload.

Object Lock stores objects in a write-once-read-many (WORM) model. Once an object is locked, it cannot be deleted or overwritten until its retention period ends; in *compliance* mode not even the root user can remove it early. If it were enabled, a user who deletes a note from the dashboard would have the request rejected, and the note would stay in the bucket against their wishes. Object Lock also cannot be turned off once it is enabled on a bucket, so leaving it disabled now keeps both options open.

Object Lock is meant for records that must be kept by regulation (e.g. audit logs or financial records), which personal research notes are not. Versioning already covers accidental deletes without stopping intentional ones.

## Deletion policy

The bucket uses `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain`. Deleting or replacing the CloudFormation stack leaves the bucket and the users' notes in place, and it must be emptied and deleted manually if no longer needed.

## Tags

| Key | Value |
|---|---|
| Name | `stock-research-bucket` |
| Project | `stock-research-dashboard` (`ProjectName` parameter) |
| Environment | `Prod` (`Environment` parameter) |
| Team | `DevOps` (`Team` parameter) |
| DataClassification | `private` |
| CostCenter | Same as Project (`ProjectName` parameter) |

## Outputs

| Output | Description |
|---|---|
| `BucketName` | Name of the bucket, for the dashboard's upload configuration. |
| `BucketArn` | ARN of the bucket, for IAM policies. |
