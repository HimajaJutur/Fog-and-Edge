import boto3

# Region
REGION = "us-east-1"

# Create SNS client
sns = boto3.client("sns", region_name=REGION)

# Your email
EMAIL = "himajajutur@gmail.com"   # 🔴 CHANGE THIS

# Topic name
TOPIC_NAME = "DataCenterAlerts"


def create_sns():
    print("🚀 Creating SNS Topic...")

    # Create topic
    response = sns.create_topic(Name=TOPIC_NAME)
    topic_arn = response["TopicArn"]

    print("✅ Topic Created:", topic_arn)

    # Create subscription
    print("📩 Subscribing email...")
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=EMAIL
    )

    print("⚠ Check your email and CONFIRM subscription!")

    return topic_arn


if __name__ == "__main__":
    arn = create_sns()

    print("\n🎯 NEXT STEP:")
    print("Copy this ARN and add to Lambda environment variable:")
    print("SNS_TOPIC_ARN =", arn)