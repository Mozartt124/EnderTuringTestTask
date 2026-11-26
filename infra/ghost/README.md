# Ghost on AWS

One CloudFormation stack: a VPC with a public subnet, one EC2 instance
(Amazon Linux 2023, `t3.small`) running Ghost, MySQL and nginx in Docker, an
Elastic IP, and an instance role for SSM Session Manager. Only port 80 is open;
there is no SSH and no key pair.

Ghost (`ghost:6-alpine`) and MySQL (`mysql:8.0.46`, pinned by digest) match
Ghost's official [Docker Compose file](https://github.com/TryGhost/ghost-docker/blob/main/compose.yml).
Image changes only apply to new stacks: setup runs once, on first boot, and
MySQL cannot open a data directory written by a newer major version.

## Prerequisites

- AWS CLI v2 with credentials and a default region (`aws sts get-caller-identity` works)
- Permission to create EC2, VPC, EIP, IAM role and CloudFormation resources
- [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) for the tunnel and shell
- `bash` and `curl`

## Deploy

```bash
cd infra/ghost
./deploy.sh
```

The script creates or updates the stack `ghost-blog`, then waits up to 15
minutes until Ghost answers at its public URL and prints it. If Ghost does not
come up in time, it prints the instance status and container logs (via SSM),
then exits non-zero. Rerunning is safe; an unchanged stack is left alone.
Optional: `STACK_NAME`, `INSTANCE_TYPE`, `WAIT_TIMEOUT` (seconds).

## Verify

Public access (any browser, or):

```bash
URL=$(aws cloudformation describe-stacks --stack-name ghost-blog \
  --query "Stacks[0].Outputs[?OutputKey=='PublicUrl'].OutputValue" --output text)
curl -s "$URL/" | grep -o '<meta name="generator" content="Ghost[^"]*"'
curl -s -o /dev/null -w '%{http_code}\n' "$URL/ghost/"   # 404: admin is not public
```

Admin tunnel (keep it running, then open <http://localhost:2368/ghost/> and
create the owner account first):

```bash
ID=$(aws cloudformation describe-stacks --stack-name ghost-blog \
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)
aws ssm start-session --target "$ID" --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["2368"],"localPortNumber":["2368"]}'
```

Shell on the instance: `aws ssm start-session --target "$ID"`.

## Limitations

- **Plain HTTP.** Without a domain there is no TLS certificate, so reader
  traffic is unencrypted. The Ghost admin and Admin API are therefore blocked
  on the public endpoint and only reachable through the encrypted SSM tunnel.
- No email is configured, so staff invites, password resets and member
  sign-in links are not sent.

## Delete

```bash
aws cloudformation delete-stack --stack-name ghost-blog
aws cloudformation wait stack-delete-complete --stack-name ghost-blog
```

**All blog data is deleted with the stack.** Posts, images and the MySQL
database live on the instance's root volume, which is removed with the
instance, and the Elastic IP is released. To keep the blog, export it first
(Ghost admin → Settings → Import/Export) and copy `/opt/ghost/content/images`,
which the export does not include.
