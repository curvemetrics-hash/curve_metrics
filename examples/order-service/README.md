# Order Service (Sample Developer Codebase)

A real-world microservice demonstrating how a developer uses **Curve Metrics** to provision cloud infrastructure (PostgreSQL DB, S3 Storage Bucket, IAM, and Kubernetes namespace) without writing complex Terraform or waiting for DevOps tickets.

---

## 📂 Project Structure

```text
order-service/
├── app.py              # Application microservice (Health check, Orders API, S3 receipt handler)
├── Dockerfile          # Production container build
├── curvemetrics.yaml   # Infrastructure contract: tells Curve Metrics what resources to provision
├── deployment.yaml     # Kubernetes deployment consuming injected cloud config & secrets
└── README.md           # Developer onboarding guide
```

---

## 🚀 How to Move Forward (Step-by-Step)

### Step 1: Run the Code Locally
You can test the application locally in 1 second:
```bash
python app.py
```
Visit `http://localhost:8080/health` or `http://localhost:8080/api/orders`.

---

### Step 2: Request Cloud Infrastructure via Curve Metrics

You have two ways to provision this in the cloud:

#### Option A: Via the Web UI (Easiest)
1. Open [**https://curve-metrics.pages.dev**](https://curve-metrics.pages.dev) (or [Render](https://curve-metrics-platform.onrender.com)).
2. Click **Launch Platform Console** (sign in with `admin` / `admin123`).
3. Click **+ New Environment** and enter:
   - **Environment Name**: `checkout-dev`
   - **Team**: `checkout`
   - **Tier**: `dev`
   - **Size Preset**: `small`
   - **Blueprint**: `standard`
   - **Admin Group**: `checkout-admins`
4. Click **Create & Run Pipeline**.

#### Option B: Via the API (CLI / CI/CD)
```bash
curl -X POST https://curve-metrics-platform.onrender.com/spaces \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "name": "checkout-dev",
    "team": "checkout",
    "environment": "dev",
    "size": "small",
    "blueprint": "standard",
    "admin_groups": ["checkout-admins"]
  }'
```

---

### Step 3: Curve Metrics Autonomous Provisioning
Once submitted, Curve Metrics:
1. Runs the **10-stage provisioning pipeline** (Format $\rightarrow$ Validate $\rightarrow$ Plan $\rightarrow$ Security Policy Gate $\rightarrow$ Apply $\rightarrow$ Verify).
2. Deploys the isolated Kubernetes namespace `checkout-dev`.
3. Creates the PostgreSQL database (`orders_db`) and S3 Bucket (`checkout-orders-receipts`).
4. Injects connection credentials into a ConfigMap `curve-cloud-resources` and Secret `curve-app-secrets`.

---

### Step 4: Deploy Your App
Your deployment in `deployment.yaml` binds to those injected environment variables automatically:
```yaml
envFrom:
  - configMapRef:
      name: curve-cloud-resources
  - secretRef:
      name: curve-app-secrets
```
The application boots up, connects to PostgreSQL and S3, and handles live traffic!
