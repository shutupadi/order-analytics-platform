# Deploying on AWS (EC2 + RDS + Lambda + S3)

The code runs locally with no AWS account. These are the steps to host it on AWS.
Use one region for everything (e.g. `ap-south-1`, Mumbai). Free-tier sizes are enough.

```
            Users / Postman
                  │  HTTP
                  ▼
   ┌─────────────────────────┐        ┌──────────────────────────┐
   │ EC2  (Flask + gunicorn) │──SQL──►│ RDS PostgreSQL           │
   │ order-management API    │        │ customers, products,     │
   └─────────────────────────┘        │ inventory, orders, items │
                                      └────────────▲─────────────┘
   EventBridge (daily 1 AM) ──► Lambda ETL ────────┘ extract
                                   │ transform + quality checks
                                   ▼ load
                         S3  s3://<bucket>/powerbi/*.csv
                                   │
                                   ▼
                             Power BI dashboard
```

## 1. RDS (the database)
1. RDS → Create database → **PostgreSQL 16**, template **Free tier**, instance `db.t3.micro`.
2. DB name `orders`, set a master username and password.
3. Public access: **No**. Note the endpoint, e.g. `orders-db.xxxx.ap-south-1.rds.amazonaws.com`.
4. Security group: allow port **5432** only from the EC2 and Lambda security groups.

Connection string used by the app and ETL:
```
DATABASE_URL=postgresql+psycopg://<user>:<password>@<rds-endpoint>:5432/orders
```

## 2. EC2 (the API)
1. EC2 → Launch instance → **Amazon Linux 2023**, `t2.micro`. Security group: allow port 22 (your IP) and 8000 (or 80 behind nginx).
2. SSH in and run:
   ```bash
   sudo dnf install -y git python3.12 python3.12-pip
   git clone https://github.com/<you>/order-analytics-platform.git && cd order-analytics-platform
   python3.12 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   export DATABASE_URL=postgresql+psycopg://<user>:<password>@<rds-endpoint>:5432/orders
   python seed.py                                   # creates tables + demo data in RDS
   gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
   ```
3. Test: `http://<ec2-public-ip>:8000/reports/monthly_revenue`.
   (For a permanent setup, run gunicorn as a systemd service.)

## 3. S3 (where Power BI files land)
1. S3 → Create bucket, e.g. `order-analytics-exports-<yourname>`. Keep "Block public access" ON.
2. The ETL writes `powerbi/fact_sales.csv`, `dim_customer.csv`, `dim_product.csv`, `dim_date.csv`, `inventory_snapshot.csv`, overwriting them each run so Power BI always refreshes from the same paths.

## 4. Lambda (the ETL job)
1. Lambda → Create function → Python 3.12, name `orders-etl`.
2. **Code**: zip `app/` and `etl/` folders and upload. Handler: `etl.etl_job.lambda_handler`.
3. **Libraries**: add the AWS-managed layer **AWSSDKPandas-Python312** (gives pandas). Add `sqlalchemy` and `psycopg[binary]` in your own layer (`pip install -t python/ sqlalchemy "psycopg[binary]"` on Linux, zip the `python/` folder).
4. **Environment variables**: `DATABASE_URL` (RDS), `S3_BUCKET` (bucket name).
5. **Permissions**: execution role needs `s3:PutObject` on the bucket. Put the Lambda in the same VPC as RDS (and add an S3 VPC gateway endpoint so it can reach S3).
6. Timeout: 1 minute, memory 512 MB.
7. **Schedule**: EventBridge → Rules → schedule `cron(0 20 * * ? *)` (01:30 IST daily) → target `orders-etl`.

## 5. Power BI
See [POWER_BI_GUIDE.md](POWER_BI_GUIDE.md). Download the CSVs from S3 (or sync them to a folder / SharePoint) and point Power BI at them. Alternatively, Power BI can connect straight to RDS PostgreSQL.

## Cost / clean-up
All of the above fits the AWS free tier for small usage. Stop the EC2 and RDS instances when not demoing.
