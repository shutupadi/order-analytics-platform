import os

# Local default: a SQLite file. On AWS: point this at RDS PostgreSQL, e.g.
# postgresql+psycopg://user:password@mydb.xxxxx.ap-south-1.rds.amazonaws.com:5432/orders
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///orders.db")

# If set, the ETL job uploads CSVs to this S3 bucket. If empty, it writes to ./exports
S3_BUCKET = os.getenv("S3_BUCKET", "")
EXPORT_DIR = os.getenv("EXPORT_DIR", "exports")
