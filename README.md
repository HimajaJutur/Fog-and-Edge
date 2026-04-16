# 🌡️ Fog-Based Data Center Thermal Monitoring System using AWS

A student-level Fog & Edge Computing project demonstrating:
- **Sensor simulation** → **Fog Node (Flask)** → **AWS (API Gateway + Lambda + DynamoDB)**
- Real-time dashboard with live charts

---

## 📁 Project Structure

```
fog-thermal-monitor/
├── sensors/
│   └── sensor_simulator.py     # Simulates 5 sensors
├── fog_node/
│   └── fog_node.py             # Fog processing layer (Flask, port 5000)
├── lambda/
│   └── lambda_function.py      # AWS Lambda handler
├── dashboard/
│   ├── dashboard_app.py        # Dashboard web server (Flask, port 8080)
│   └── templates/
│       └── index.html          # Live monitoring UI
├── requirements.txt
└── README.md
```

---

## 🏗️ Architecture

```
[Python Sensor Script]
        │  HTTP POST every 2s
        ▼
[Fog Node - Flask :5000]          ← LOCAL (your laptop / edge server)
   • Classify: NORMAL/WARNING/CRITICAL
   • Filter redundant NORMAL data
   • Only forward meaningful data
        │  HTTP POST (filtered)
        ▼
[AWS API Gateway]                 ← CLOUD (AWS Learner Lab)
        │
        ▼
[AWS Lambda]
   • Validate payload
   • Write to DynamoDB
        │
        ▼
[DynamoDB Table: ThermalMonitorData]

[Dashboard - Flask :8080]         ← LOCAL
   • Polls fog node every 2s
   • Shows live chart + fog stats
```

---

## 🔧 LOCAL SETUP

### 1. Install Python dependencies

```bash
pip install flask requests boto3
```

### 2. Start the Fog Node

```bash
cd fog_node
python fog_node.py
```
> Runs at `http://127.0.0.1:5000`

### 3. Start the Dashboard

```bash
cd dashboard
python dashboard_app.py
```
> Open `http://127.0.0.1:8080` in your browser

### 4. Start the Sensor Simulator

```bash
cd sensors

# Normal scenario
python sensor_simulator.py --scenario normal --interval 2

# Warning scenario
python sensor_simulator.py --scenario warning

# Critical scenario
python sensor_simulator.py --scenario critical

# Random mix (default)
python sensor_simulator.py
```

---

## ☁️ AWS SETUP (Learner Lab — Step by Step)

### STEP 1 — Create DynamoDB Table

1. Open **AWS Console** → search **DynamoDB** → click **Create table**
2. Fill in:
   - **Table name:** `ThermalMonitorData`
   - **Partition key:** `sensor_id` (String)
   - **Sort key:** `timestamp` (String)
3. Leave everything else as default → click **Create table**
4. Wait until status shows **Active** ✅

---

### STEP 2 — Create Lambda Function

1. Open **AWS Console** → search **Lambda** → click **Create function**
2. Choose **Author from scratch**
3. Fill in:
   - **Function name:** `ThermalMonitorHandler`
   - **Runtime:** `Python 3.12`
   - **Architecture:** x86_64
4. Click **Create function**
5. In the **Code** tab, delete the default code
6. Paste the entire contents of `lambda/lambda_function.py`
7. Click **Deploy**

#### Add Environment Variable (optional but good practice)
- Go to **Configuration** → **Environment variables** → **Edit**
- Add: `DYNAMODB_TABLE` = `ThermalMonitorData`
- Click **Save**

#### Set Lambda Permissions
- Go to **Configuration** → **Permissions**
- Click the **Role name** link (opens IAM)
- Click **Add permissions** → **Attach policies**
- Search `AmazonDynamoDBFullAccess` → check it → **Add permissions**

#### Test the Lambda
- Go back to Lambda → **Test** tab
- Create a new test event named `TestEvent` with this body:
```json
{
  "httpMethod": "POST",
  "body": "{\"sensor_id\":\"RACK-01\",\"timestamp\":\"2024-01-01T12:00:00Z\",\"temperature\":75.5,\"humidity\":55.0,\"airflow\":45.0,\"cpu_load\":70.0,\"heat_index\":78.3,\"status\":\"WARNING\",\"alerts\":[\"WARNING: High temp\"]}"
}
```
- Click **Test** — you should see `"message": "Data stored successfully"`
- Check DynamoDB → your table should have one record ✅

---

### STEP 3 — Create API Gateway

1. Open **AWS Console** → search **API Gateway** → **Create API**
2. Choose **HTTP API** (simpler) → click **Build**
3. Fill in:
   - **API name:** `ThermalMonitorAPI`
4. Click **Next** → **Next** → **Create**

#### Add a Route + Integration
1. In the API, go to **Routes** → **Create**
2. Method: `POST`, Path: `/thermal-data` → **Create**
3. Click on the route → **Create and attach an integration**
4. Integration type: **Lambda function**
5. Select your Lambda: `ThermalMonitorHandler`
6. Click **Create**

#### Enable CORS (important)
1. Go to **CORS** in the left sidebar
2. Click **Configure**
3. Set:
   - **Allow origins:** `*`
   - **Allow methods:** `POST, OPTIONS`
   - **Allow headers:** `Content-Type`
4. Click **Save**

#### Deploy
1. Go to **Deploy** → **Create and deploy**
2. Stage name: `prod`
3. Note your **Invoke URL** — it looks like:
   `https://abc123xyz.execute-api.us-east-1.amazonaws.com`

Your full endpoint is:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/thermal-data
```

---

### STEP 4 — Connect Fog Node to AWS

Edit `fog_node/fog_node.py` line ~18:

```python
AWS_API_GATEWAY_URL = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/thermal-data"
```

Replace with your actual URL from Step 3.

**OR** set an environment variable (better):
```bash
export AWS_API_GATEWAY_URL="https://abc123xyz.execute-api.us-east-1.amazonaws.com/thermal-data"
python fog_node.py
```

---

### STEP 5 — Test the Full Pipeline

1. Start fog node: `python fog_node/fog_node.py`
2. Start dashboard: `python dashboard/dashboard_app.py`
3. Start sensor (critical scenario to see alerts):
   ```bash
   python sensors/sensor_simulator.py --scenario critical
   ```
4. Open `http://127.0.0.1:8080` — watch the dashboard update live
5. Check DynamoDB table — records should appear in real time ✅

---

## 📊 How to View Data in DynamoDB

1. Open DynamoDB → **Tables** → `ThermalMonitorData`
2. Click **Explore table items**
3. You'll see all records with sensor_id, timestamp, status, temperature, etc.

---

## 🧠 Key Concepts Demonstrated

| Concept | Implementation |
|---------|----------------|
| **Fog/Edge Processing** | Flask fog node classifies data before cloud |
| **Data Filtering** | NORMAL readings with <3°C change are dropped |
| **Serverless Cloud** | API Gateway + Lambda (no servers to manage) |
| **NoSQL Storage** | DynamoDB stores all processed readings |
| **Real-time Dashboard** | Chart.js plots temperature history live |
| **Anomaly Detection** | Sensor rejects 0 or out-of-range values |

---

## ⚙️ Configuration Reference

| Variable | File | Default | Description |
|----------|------|---------|-------------|
| `FOG_NODE_URL` | `sensor_simulator.py` | `127.0.0.1:5000` | Fog node address |
| `SEND_INTERVAL` | `sensor_simulator.py` | `2` | Seconds between sensor reads |
| `AWS_API_GATEWAY_URL` | `fog_node.py` | placeholder | Your API Gateway URL |
| `TEMP_CRITICAL` | `fog_node.py` | `80` | °C threshold for CRITICAL |
| `TEMP_WARNING` | `fog_node.py` | `70` | °C threshold for WARNING |
| `AIRFLOW_LOW` | `fog_node.py` | `40` | % below = low airflow |
| `DYNAMODB_TABLE` | Lambda env var | `ThermalMonitorData` | DynamoDB table name |

---

## 🚨 Troubleshooting

**Fog node can't reach AWS:**
- Verify `AWS_API_GATEWAY_URL` is correct
- Check API Gateway is deployed to `prod` stage
- Check Lambda permissions include DynamoDB

**Lambda errors:**
- Go to Lambda → **Monitor** → **View CloudWatch logs**
- Look for Python errors

**DynamoDB no records:**
- Check Lambda test passed first
- Check table name matches env var

**Dashboard shows no data:**
- Make sure fog node is running on port 5000
- Check browser console for errors

---

## 📝 Notes for AWS Learner Lab

- Learner Lab sessions expire — you may need to redeploy after restarting
- IAM roles are auto-created — just add DynamoDB permissions as shown
- API Gateway HTTP API is free-tier eligible
- Lambda free tier: 1M requests/month
- DynamoDB free tier: 25 GB storage, 25 read/write capacity units
