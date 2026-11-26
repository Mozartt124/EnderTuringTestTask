#!/usr/bin/env bash
# Create or update the Ghost stack, then wait until the blog answers publicly.
# Safe to rerun: an unchanged stack is left as is, and the AMI chosen at
# creation is kept so updates never replace the instance and its data.
set -euo pipefail

STACK_NAME="${STACK_NAME:-ghost-blog}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-900}" # seconds to wait for Ghost once the stack is ready
AMI_PARAMETER="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
TEMPLATE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/template.yaml"

log() { printf '==> %s\n' "$*" >&2; }
die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

stack_status() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo NONE
}

stack_output() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

print_failed_events() {
  aws cloudformation describe-stack-events --stack-name "$STACK_NAME" --max-items 15 \
    --query "StackEvents[?contains(ResourceStatus, 'FAILED')].[LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
    --output table >&2 || true
}

LAST_RESULT="no response yet"
ghost_is_up() {
  local out code
  if ! out="$(curl -sS --max-time 10 -w '\n%{http_code}' "$PUBLIC_URL/" 2>&1)"; then
    LAST_RESULT="${out%%$'\n'*}"
    return 1
  fi
  code="${out##*$'\n'}"
  LAST_RESULT="HTTP $code"
  # Ghost marks its pages with <meta name="generator" content="Ghost x.y">.
  [[ "$code" == 200 && "$out" == *'content="Ghost'* ]]
}

diagnose() {
  set +e
  log "Ghost did not answer at $PUBLIC_URL within ${WAIT_TIMEOUT}s (last result: $LAST_RESULT)."
  log "Instance $INSTANCE_ID state / system check / instance check:"
  aws ec2 describe-instance-status --instance-ids "$INSTANCE_ID" --include-all-instances \
    --query 'InstanceStatuses[0].[InstanceState.Name,SystemStatus.Status,InstanceStatus.Status]' \
    --output text >&2

  local ping
  ping="$(aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null)"
  if [[ "$ping" == Online ]]; then
    log "Collecting container status and logs via SSM Run Command:"
    local command_id
    command_id="$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
      --document-name AWS-RunShellScript --comment "ghost deploy diagnostics" \
      --parameters '{"commands":["docker ps -a","echo --- ghost; docker logs --tail 40 ghost 2>&1","echo --- ghost-db; docker logs --tail 15 ghost-db 2>&1","echo --- ghost-web; docker logs --tail 15 ghost-web 2>&1","echo --- cloud-init; tail -n 30 /var/log/cloud-init-output.log"]}' \
      --query Command.CommandId --output text)"
    aws ssm wait command-executed --command-id "$command_id" --instance-id "$INSTANCE_ID"
    aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
      --query StandardOutputContent --output text >&2
  else
    log "SSM agent is not online (status: ${ping:-unknown}). Latest console output:"
    aws ec2 get-console-output --instance-id "$INSTANCE_ID" --latest \
      --query Output --output text 2>&1 | tail -n 40 >&2
  fi
  log "Rerun ./deploy.sh to keep waiting, or open a shell: aws ssm start-session --target $INSTANCE_ID"
}

for cmd in aws curl; do
  command -v "$cmd" >/dev/null || die "'$cmd' is required but not installed."
done
aws sts get-caller-identity --query Account --output text >/dev/null ||
  die "AWS credentials are not configured (aws sts get-caller-identity failed)."
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region || true)}}"
[[ -n "$REGION" ]] || die "No AWS region configured (set AWS_REGION or run 'aws configure')."
export AWS_REGION="$REGION"
log "Stack '$STACK_NAME' in $REGION"

status="$(stack_status)"
case "$status" in
  ROLLBACK_COMPLETE)
    # A failed first creation leaves an empty stack that cannot be updated.
    log "Removing stack left in ROLLBACK_COMPLETE by a failed creation"
    aws cloudformation delete-stack --stack-name "$STACK_NAME"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
    status=NONE
    ;;
  *_IN_PROGRESS)
    [[ "$status" == REVIEW_IN_PROGRESS ]] ||
      die "Stack is $status. Wait for it to finish, then rerun."
    ;;
esac

params=()
if [[ "$status" == NONE || "$status" == REVIEW_IN_PROGRESS ]]; then
  ami="$(aws ssm get-parameter --name "$AMI_PARAMETER" --query Parameter.Value --output text)"
  log "Creating stack with Amazon Linux 2023 AMI $ami"
  params+=("ImageId=$ami")
else
  log "Updating existing stack ($status); keeping its AMI"
fi
if [[ -n "${INSTANCE_TYPE:-}" ]]; then
  params+=("InstanceType=$INSTANCE_TYPE")
fi

if ! aws cloudformation deploy --stack-name "$STACK_NAME" --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
  ${params[@]+--parameter-overrides "${params[@]}"}; then
  log "CloudFormation deployment failed. Recent failure events:"
  print_failed_events
  exit 1
fi

PUBLIC_URL="$(stack_output PublicUrl)"
INSTANCE_ID="$(stack_output InstanceId)"
log "Waiting up to ${WAIT_TIMEOUT}s for Ghost at $PUBLIC_URL (first boot takes a few minutes)"

deadline=$((SECONDS + WAIT_TIMEOUT))
next_report=$SECONDS
until ghost_is_up; do
  if ((SECONDS >= deadline)); then
    diagnose
    exit 1
  fi
  if ((SECONDS >= next_report)); then
    log "Not ready yet ($LAST_RESULT); $((deadline - SECONDS))s left"
    next_report=$((SECONDS + 60))
  fi
  sleep 10
done

cat <<EOF

Ghost is up: $PUBLIC_URL

Instance:     $INSTANCE_ID
Admin tunnel: $(stack_output AdminTunnelCommand)
              then open http://localhost:2368/ghost/ (finish the owner setup there first)
Shell:        aws ssm start-session --target $INSTANCE_ID
EOF
