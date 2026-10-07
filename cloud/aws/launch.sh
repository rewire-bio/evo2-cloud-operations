#!/usr/bin/env bash
# Run the Evo 2 workloads on one EC2 GPU instance, copy results back, and delete everything.
#
# Required environment:
#   PLATFORM_ID     e.g. P1
#   INSTANCE_TYPE   e.g. p5.4xlarge (1 x H100 80 GB) or g6e.2xlarge (1 x L40S 48 GB)
#   AWS_REGION      e.g. us-east-1
#   AWS_PROFILE     a profile with EC2 permissions in a Rewire account
#   IMAGE_REF       container image pinned by digest
#   BUNDLE, OUT     local input bundle and output directories
#   CODE_SHA256     hash of code.tar.gz
# Optional: MAX_HOURS (default 3), DISK_GB (default 200)
set -euo pipefail
source "$(dirname "$0")/../common.sh"

MAX_HOURS=${MAX_HOURS:-3}
DISK_GB=${DISK_GB:-200}
NAME="evo2ops-$(lower "$PLATFORM_ID")-$(date -u +%Y%m%d%H%M%S)"
mkdir -p "$OUT"
KEY="$OUT/.ssh-key"
aws_() { aws --region "$AWS_REGION" --output text "$@"; }

INSTANCE_ID="" SG_ID=""
cleanup() {
  set +e
  if [[ -n $INSTANCE_ID ]]; then
    log "Terminating $INSTANCE_ID"
    aws_ ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
    aws_ ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"
    mark terminated
  fi
  [[ -n $SG_ID ]] && aws_ ec2 delete-security-group --group-id "$SG_ID"
  aws_ ec2 delete-key-pair --key-name "$NAME" >/dev/null
  rm -f "$KEY" "$KEY.pub"
}
trap cleanup EXIT

# 1. Machine image: AWS Deep Learning Base OSS AMI (NVIDIA driver, Docker, NVIDIA container toolkit).
AMI=$(aws_ ssm get-parameter --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id --query Parameter.Value)
ROOT_DEVICE=$(aws_ ec2 describe-images --image-ids "$AMI" --query 'Images[0].RootDeviceName')
log "AMI $AMI ($ROOT_DEVICE)"

# 2. One-off SSH key and a security group that admits SSH from this machine only.
new_ssh_key
aws_ ec2 import-key-pair --key-name "$NAME" --public-key-material "fileb://$KEY.pub" >/dev/null
MY_IP=$(curl -fsS https://checkip.amazonaws.com)
VPC=$(aws_ ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')
SG_ID=$(aws_ ec2 create-security-group --group-name "$NAME" --description "evo2ops SSH" --vpc-id "$VPC" --query GroupId)
aws_ ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP/32" >/dev/null

# 3. Launch. Try each default subnet (one per availability zone) until capacity is found.
#    Shutdown from inside the instance terminates it, and the OS timer shuts it down after MAX_HOURS.
USER_DATA="#!/bin/bash
shutdown -h +$((MAX_HOURS * 60))"
mark launch_requested
for SUBNET in $(aws_ ec2 describe-subnets --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true --query 'Subnets[].SubnetId'); do
  if INSTANCE_ID=$(aws_ ec2 run-instances \
      --image-id "$AMI" --instance-type "$INSTANCE_TYPE" --count 1 \
      --subnet-id "$SUBNET" --security-group-ids "$SG_ID" --key-name "$NAME" \
      --associate-public-ip-address \
      --instance-initiated-shutdown-behavior terminate \
      --metadata-options HttpTokens=required \
      --block-device-mappings "[{\"DeviceName\":\"$ROOT_DEVICE\",\"Ebs\":{\"VolumeSize\":$DISK_GB,\"VolumeType\":\"gp3\",\"Throughput\":500,\"Iops\":6000,\"DeleteOnTermination\":true}}]" \
      --user-data "$USER_DATA" \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=project,Value=evo2-cloud-operations}]" \
      --query 'Instances[0].InstanceId' 2>"$OUT/run-instances.err"); then
    break
  fi
  log "No capacity in $SUBNET: $(tail -1 "$OUT/run-instances.err")"
  INSTANCE_ID=""
done
[[ -n $INSTANCE_ID ]] || { log "Could not launch $INSTANCE_TYPE in $AWS_REGION"; exit 3; }
aws_ ec2 wait instance-running --instance-ids "$INSTANCE_ID"
mark running
read -r IP AZ < <(aws_ ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].[PublicIpAddress,Placement.AvailabilityZone]')
cat > "$OUT/instance.json" <<EOF
{"provider": "aws", "instance_type": "$INSTANCE_TYPE", "region": "$AWS_REGION", "zone": "$AZ",
 "instance_id": "$INSTANCE_ID", "image": "$AMI", "purchase_option": "on-demand", "disk_gb": $DISK_GB}
EOF
log "$INSTANCE_ID running in $AZ at $IP"

SSH_USER=ubuntu SSH_HOST=$IP SSH_PORT=22

# 4. Run, copy results back. cleanup() terminates the instance whatever happens.
wait_for_ssh
run_bundle docker
