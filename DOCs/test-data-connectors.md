# Test Data Connectors and Resolver

The connector layer fetches valid test data before browser exploration starts.

Source files:

```text
agent/connectors/
agent/nodes/test_data_connector.py
agent/nodes/test_data_resolver.py
agent/config/data_sources.yaml
agent/utils/data_masking.py
agent/utils/schema_validator.py
```

## Goals

- Use deterministic code to fetch data.
- Do not let the LLM read files, query databases, call APIs, or access secrets.
- Do not invent random browser input.
- Stop at HITL when required data is missing.
- Mask secrets in logs and reports.

## Resolver Priority

The resolver checks sources in this order:

```text
1. Inline user-provided data
2. Environment variables
3. JSON files
4. CSV files
5. Database using predefined named queries only
6. External API using predefined operations only
7. Synthetic data, only if safe
8. HITL missing-data request
```

## Connector Interface

Every connector implements:

```python
from abc import ABC, abstractmethod
from typing import Any

class BaseConnector(ABC):
    @abstractmethod
    def can_handle(self, request: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        pass
```

Success response:

```json
{
  "status": "success",
  "source": "json",
  "data": {
    "username": "qa_customer_01",
    "passwordEnv": "QA_CUSTOMER_PASSWORD",
    "role": "customer"
  },
  "alias": "validCustomer"
}
```

Missing response:

```json
{
  "status": "missing",
  "source": "json",
  "reason": "No matching user record found."
}
```

## Data Source Configuration

Configuration lives in:

```text
agent/config/data_sources.yaml
```

Example:

```yaml
environment: qa

sources:
  inline:
    enabled: true

  env:
    enabled: true
    keys:
      customer_username: QA_CUSTOMER_USERNAME
      customer_password: QA_CUSTOMER_PASSWORD
      test_data_api_token: TEST_DATA_API_TOKEN
      db_connection_string: QA_DB_CONNECTION_STRING

  json:
    enabled: true
    paths:
      users: generated-tests/test-data/users.json
      products: generated-tests/test-data/products.json
      checkout: generated-tests/test-data/checkout-data.json

  csv:
    enabled: true
    paths:
      users: data/users.csv
      products: data/products.csv
      checkout: data/checkout-data.csv

  database:
    enabled: false
    type: postgres
    connection_env_var: QA_DB_CONNECTION_STRING
    allowed_queries:
      - get_active_customer
      - get_in_stock_product
      - get_customer_with_balance

  api:
    enabled: false
    base_url_env_var: TEST_DATA_API_URL
    token_env_var: TEST_DATA_API_TOKEN
    allowed_operations:
      - get_active_customer
      - get_in_stock_product
      - create_test_customer
      - setup_cart
```

If `PyYAML` is not installed, the agent falls back to the same built-in default config. Install full dependencies with:

```bash
pip install -r requirements.txt
```

## Inline Data

Inline data is passed at runtime with `--test-data`.

Example:

```bash
python -m agent run ^
  --url "https://qa.example.com" ^
  --flow "Log in as a customer and search for an in-stock product" ^
  --test-data "{\"user\":{\"username\":\"qa_customer_01\",\"password\":\"runtime-only\",\"role\":\"customer\",\"status\":\"active\"}}"
```

Recommended shape:

```json
{
  "user": {
    "username": "qa_customer_01",
    "password": "runtime-only",
    "role": "customer",
    "status": "active"
  },
  "product": {
    "sku": "QA-LAPTOP-001",
    "name": "QA Laptop",
    "searchTerm": "laptop",
    "status": "inStock"
  }
}
```

Do not commit real secrets. Prefer runtime environment variables for passwords.

## Environment Connector

Source file:

```text
agent/connectors/env_connector.py
```

The environment connector maps logical fields to configured environment variables.

Example `.env.example`:

```text
QA_CUSTOMER_USERNAME=
QA_CUSTOMER_PASSWORD=
QA_DB_CONNECTION_STRING=
TEST_DATA_API_URL=
TEST_DATA_API_TOKEN=
BASE_URL=
APP_URL=
```

Example runtime:

```bash
set QA_CUSTOMER_USERNAME=qa_customer_01
set QA_CUSTOMER_PASSWORD=runtime-only
python -m agent run --url "https://qa.example.com" --flow "Log in as a customer"
```

The connector can resolve:

- `username`
- `email`
- `password`
- `token`
- `connectionString`

## JSON Connector

Source file:

```text
agent/connectors/json_connector.py
```

Configured paths:

```text
generated-tests/test-data/users.json
generated-tests/test-data/products.json
generated-tests/test-data/checkout-data.json
```

Example users file:

```json
{
  "users": [
    {
      "alias": "validCustomer",
      "username": "qa_customer_01",
      "passwordEnv": "QA_CUSTOMER_PASSWORD",
      "role": "customer",
      "status": "active"
    }
  ]
}
```

Example products file:

```json
{
  "products": [
    {
      "alias": "inStockProduct",
      "sku": "QA-LAPTOP-001",
      "name": "QA Laptop",
      "searchTerm": "laptop",
      "status": "inStock"
    }
  ]
}
```

Rules:

- Read configured paths only.
- Filter records by constraints.
- Validate required fields.
- Return the first matching valid record.
- Hydrate `passwordEnv` only if the environment variable exists.

## CSV Connector

Source file:

```text
agent/connectors/csv_connector.py
```

Example CSV:

```csv
alias,username,passwordEnv,role,status
validCustomer,qa_customer_01,QA_CUSTOMER_PASSWORD,customer,active
```

Rules:

- Read configured CSV paths only.
- Use header names as field names.
- Filter rows by constraints.
- Validate required fields.
- Return the first matching valid row.

## Database Connector

Source file:

```text
agent/connectors/db_connector.py
```

Database access is controlled.

Rules:

- Read-only access only.
- No arbitrary SQL.
- No SQL generated by an LLM.
- Use predefined named queries only.
- Connection string comes from an environment variable.
- Query parameters are derived from validated constraints.
- Passwords are not returned from database results.

Allowed query map:

```python
ALLOWED_QUERIES = {
    "get_active_customer": """
        SELECT username, role
        FROM qa_test_users
        WHERE status = 'ACTIVE'
        AND role = :role
        LIMIT 1
    """,
    "get_in_stock_product": """
        SELECT sku, name, searchTerm
        FROM qa_products
        WHERE status = 'IN_STOCK'
        LIMIT 1
    """
}
```

Example config for SQLite QA fixture data:

```yaml
database:
  enabled: true
  type: sqlite
  connection_env_var: QA_DB_CONNECTION_STRING
  allowed_queries:
    - get_active_customer
    - get_in_stock_product
```

Example environment variable:

```bash
set QA_DB_CONNECTION_STRING=sqlite:///C:/qa-fixtures/test-data.sqlite
```

Example config for Postgres:

```yaml
database:
  enabled: true
  type: postgres
  connection_env_var: QA_DB_CONNECTION_STRING
  allowed_queries:
    - get_active_customer
    - get_in_stock_product
```

Postgres requires an approved `psycopg` dependency. If the driver is not installed, the connector reports a clear missing-data reason.

## API Connector

Source file:

```text
agent/connectors/api_connector.py
```

API access is controlled.

Rules:

- No arbitrary API calls.
- No endpoint generated by an LLM.
- Base URL comes from an environment variable.
- Token comes from an environment variable.
- Only predefined operations are allowed.
- Only allowed params/body fields are sent.

Allowed operation map:

```python
ALLOWED_OPERATIONS = {
    "get_active_customer": {
        "method": "GET",
        "path": "/test-data/users",
        "allowedParams": ["role", "status"]
    },
    "get_in_stock_product": {
        "method": "GET",
        "path": "/test-data/products",
        "allowedParams": ["status", "category"]
    },
    "create_test_customer": {
        "method": "POST",
        "path": "/test-data/users",
        "allowedBodyFields": ["role", "region"]
    },
    "setup_cart": {
        "method": "POST",
        "path": "/test-data/cart/setup",
        "allowedBodyFields": ["userId", "sku"]
    }
}
```

Example environment:

```bash
set TEST_DATA_API_URL=https://qa-data.example.com
set TEST_DATA_API_TOKEN=runtime-token
```

## Resolver Output

The resolver writes one normalized state object:

```json
{
  "environment": "qa",
  "flowName": "Customer checkout flow",
  "resolvedData": {
    "user": {
      "username": "qa_customer_01",
      "password": "runtime-only",
      "role": "customer"
    },
    "product": {
      "sku": "QA-LAPTOP-001",
      "name": "QA Laptop",
      "searchTerm": "laptop"
    },
    "shippingAddress": {
      "line1": "Test Street 1",
      "city": "Pune",
      "state": "MH",
      "postalCode": "411014"
    }
  },
  "missingData": [],
  "dataSourcesUsed": ["inline", "json"]
}
```

The committed `generated-tests/test-data/resolved-test-data.json` is ignored by git and masked before writing.

## Masking

Sensitive fields are masked in reports:

```text
password
token
secret
apiKey
authorization
connectionString
otp
pin
cardNumber
cvv
```

Example masked report output:

```json
{
  "user": {
    "username": "qa_customer_01",
    "password": "********",
    "role": "customer"
  }
}
```

## Missing Data HITL

If required data is missing, the resolver writes:

```text
reports/missing_test_data.md
reports/missing_data_hitl.json
```

The browser explorer does not start.

Supported responses:

```bash
python -m agent missing-data --decision provide --data "{\"user\":{\"username\":\"qa_customer_01\",\"password\":\"runtime-only\",\"role\":\"customer\",\"status\":\"active\"}}"
python -m agent missing-data --decision skip --notes "Skip until QA user is provisioned"
python -m agent missing-data --decision synthetic --notes "Use only if syntheticAllowed is true"
python -m agent missing-data --decision change-source --notes "Enable JSON users source"
python -m agent missing-data --decision reject --notes "Blocked by MFA"
```

Secrets passed through `--data` are masked in HITL metadata.

## Reports

| Report | Purpose |
| --- | --- |
| `reports/test_data_requirements.md` | Requirements inferred from the flow |
| `reports/resolved_test_data_summary.md` | Masked resolved data and sources used |
| `reports/missing_test_data.md` | Exact missing data and sources checked |
| `reports/missing_data_hitl.json` | Human decision state for missing data |

