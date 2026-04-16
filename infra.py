

import boto3
import argparse
import sys

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
REGION     = "us-east-1"
EMAIL      = "himajajutur@gmail.com"   # Change this to your email
TOPIC_NAME = "DataCenterAlerts"


def get_sns_client():
    return boto3.client("sns", region_name=REGION)


# ─────────────────────────────────────────
# CREATE TOPIC + SUBSCRIBE
# ─────────────────────────────────────────
def create_sns(sns):
    print("Creating SNS Topic...")
    response  = sns.create_topic(Name=TOPIC_NAME)
    topic_arn = response["TopicArn"]
    print(f"Topic created: {topic_arn}")

    print(f"Subscribing {EMAIL} ...")
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=EMAIL,
    )

    print()
    print("=" * 60)
    print("IMPORTANT — ACTION REQUIRED:")
    print(f"  AWS has sent a confirmation email to: {EMAIL}")
    print("  1. Open that email (check your spam folder if not in inbox)")
    print("  2. Click 'Confirm subscription'")
    print("  3. Run this script again with --check to verify:")
    print("       python setup_sns.py --check")
    print()
    print("NEXT STEP — Add this to Lambda environment variables:")
    print(f"  SNS_TOPIC_ARN = {topic_arn}")
    print("=" * 60)

    return topic_arn


# ─────────────────────────────────────────
# CHECK SUBSCRIPTION STATUS
# ─────────────────────────────────────────
def check_subscription(sns):
    """List all topics and find subscriptions for our email."""
    print(f"Checking SNS subscription status for: {EMAIL}")
    print()

    # Find the topic
    topic_arn = None
    paginator = sns.get_paginator("list_topics")
    for page in paginator.paginate():
        for topic in page["Topics"]:
            if TOPIC_NAME in topic["TopicArn"]:
                topic_arn = topic["TopicArn"]
                break

    if not topic_arn:
        print(f"ERROR: Topic '{TOPIC_NAME}' not found in region {REGION}.")
        print("Run setup_sns.py without --check to create it first.")
        sys.exit(1)

    print(f"Topic found: {topic_arn}")

    # List subscriptions for this topic
    subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
    subscriptions = subs.get("Subscriptions", [])

    if not subscriptions:
        print("No subscriptions found for this topic.")
        print("Run setup_sns.py without --check to create a subscription.")
        sys.exit(1)

    found = False
    for sub in subscriptions:
        endpoint = sub.get("Endpoint", "")
        status   = sub.get("SubscriptionArn", "")

        if endpoint == EMAIL:
            found = True
            if status == "PendingConfirmation":
                print(f"STATUS: PendingConfirmation")
                print()
                print("Your subscription is NOT confirmed yet.")
                print(f"  1. Check inbox (and spam) for: {EMAIL}")
                print("  2. Click 'Confirm subscription' in the AWS email")
                print("  3. Re-run: python setup_sns.py --check")
            else:
                print(f"STATUS: Confirmed")
                print()
                print("Your SNS subscription is active.")
                print("Emails will be sent when CRITICAL alerts are triggered.")
                print()
                print("Lambda environment variable to set:")
                print(f"  SNS_TOPIC_ARN = {topic_arn}")

    if not found:
        print(f"No subscription found for {EMAIL}.")
        print("Run setup_sns.py without --check to subscribe.")

    return topic_arn


# ─────────────────────────────────────────
# SEND TEST ALERT
# ─────────────────────────────────────────
def send_test_alert(sns, topic_arn: str):
    """Publish a test message to verify the full pipeline end-to-end."""
    print(f"Sending test alert to {topic_arn} ...")
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Subject="TEST ALERT - Data Center Thermal Monitor",
            Message=(
                "This is a test alert from setup_sns.py.\n"
                "If you received this email, your SNS pipeline is working correctly.\n\n"
                "Sensor ID  : TEST\n"
                "Temperature: 99.0 °C\n"
                "Status     : CRITICAL\n"
            ),
        )
        print(f"Test alert sent. MessageId: {response['MessageId']}")
        print(f"Check inbox for: {EMAIL}")
    except Exception as e:
        print(f"ERROR sending test alert: {e}")
        print("Check IAM permissions and subscription status.")


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SNS Setup for Data Center Thermal Monitor")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check subscription confirmation status instead of creating",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test alert to verify end-to-end (requires confirmed subscription)",
    )
    args = parser.parse_args()

    sns = get_sns_client()

    if args.check:
        topic_arn = check_subscription(sns)
        if args.test:
            print()
            send_test_alert(sns, topic_arn)
    elif args.test:
        topic_arn = check_subscription(sns)
        send_test_alert(sns, topic_arn)
    else:
        create_sns(sns)