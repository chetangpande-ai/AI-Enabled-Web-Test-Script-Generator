# Test Data Requirements

The Test Data Requirement Node identifies data needed to execute the user flow before the browser opens.

Source file:

```text
agent/nodes/test_data_requirement.py
```

## Purpose

The node converts a high-level business flow into explicit data requirements, such as:

- Valid QA customer user
- In-stock product
- Shipping address
- Payment method
- Security-control blocker such as OTP, CAPTCHA, or MFA

This prevents the crawler from guessing invalid usernames, random product names, or unsafe payment details.

## Inputs

The node reads these fields from agent state:

```json
{
  "flow": "Log in as a customer, search for an in-stock product, add it to cart, and checkout",
  "environment": "qa",
  "data_profile": {},
  "test_data": {}
}
```

## Output Shape

The node writes `test_data_requirements` into state:

```json
[
  {
    "name": "validCustomerUser",
    "type": "user",
    "required": true,
    "fields": ["username", "password", "role"],
    "constraints": {
      "role": "customer",
      "status": "active"
    },
    "sourcePreference": ["inline", "env", "json", "database", "api"],
    "syntheticAllowed": false,
    "classification": "existing_qa_data_required",
    "reason": "A valid existing QA user is required before browser exploration."
  }
]
```

## Classifications

The node classifies requirements into these categories:

- `synthetic_data_allowed`: Safe generated data can be used, such as a non-sensitive shipping address.
- `existing_qa_data_required`: Existing QA fixture data is required, such as active users or in-stock products.
- `api_created_data_required`: A safe predefined API operation should create or fetch data.
- `db_sourced_data_required`: A safe predefined read-only DB query should fetch data.
- `user_provided_data_required`: The user must provide data, often for payment or environment-specific flows.
- `not_automatable_due_to_security_control`: The flow references OTP, CAPTCHA, MFA, or restricted access.

## Built-In Detection Rules

The current implementation is intentionally simple and deterministic.

| Flow Words | Requirement |
| --- | --- |
| `login`, `sign in`, `authenticate`, `account` | `validCustomerUser` |
| `product`, `search`, `cart`, `checkout`, `order`, `purchase` | `inStockProduct` |
| `shipping`, `address`, `delivery`, `checkout` | `shippingAddress` |
| `payment`, `card`, `cvv` | `paymentMethod` |
| `otp`, `captcha`, `mfa`, `2fa` | restricted access blocker |

## Example: Login Flow

User flow:

```text
Log in as a customer and verify the dashboard is visible.
```

Detected requirement:

```json
{
  "name": "validCustomerUser",
  "type": "user",
  "required": true,
  "fields": ["username", "password", "role"],
  "constraints": {
    "role": "customer",
    "status": "active"
  },
  "sourcePreference": ["inline", "env", "json", "database", "api"],
  "syntheticAllowed": false
}
```

## Example: Checkout Flow

User flow:

```text
Log in as a customer, search for a laptop, add an in-stock product to cart, enter shipping address, and checkout.
```

Detected requirements:

```json
[
  {
    "name": "validCustomerUser",
    "type": "user",
    "fields": ["username", "password", "role"],
    "syntheticAllowed": false
  },
  {
    "name": "inStockProduct",
    "type": "product",
    "fields": ["sku", "name", "searchTerm"],
    "syntheticAllowed": false
  },
  {
    "name": "shippingAddress",
    "type": "address",
    "fields": ["line1", "city", "state", "postalCode"],
    "syntheticAllowed": true
  }
]
```

## Example: Restricted Flow

User flow:

```text
Log in, enter OTP, and approve the transaction.
```

The node marks the flow as blocked:

```json
{
  "name": "restrictedAccess",
  "type": "restricted_access",
  "classification": "not_automatable_due_to_security_control",
  "syntheticAllowed": false,
  "reason": "The flow references OTP, CAPTCHA, MFA, or another restricted access control."
}
```

The agent must not bypass or fake OTP, CAPTCHA, MFA, or similar controls.

## Report

The node writes:

```text
reports/test_data_requirements.md
```

The report includes:

- Flow name
- Required data
- Required fields
- Constraints
- Preferred sources
- Synthetic data allowance
- Classification
- Reason

