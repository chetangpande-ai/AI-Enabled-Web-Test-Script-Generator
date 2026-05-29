# Resolved Test Data Summary

- Environment: `qa`
- Flow name: Log in as a customer and search for an in stock product
- Data sources used: `inline, json`

## Masked Resolved Data

```json
{
  "product": {
    "alias": "inStockProduct",
    "name": "QA Laptop",
    "searchTerm": "laptop",
    "sku": "QA-LAPTOP-001",
    "status": "inStock"
  },
  "user": {
    "password": "********",
    "role": "customer",
    "status": "active",
    "username": "qa_customer_01"
  }
}
```

## Assumptions

- Test data is resolved before Playwright exploration starts.
- Secrets are fetched by deterministic connectors and masked in reports.
