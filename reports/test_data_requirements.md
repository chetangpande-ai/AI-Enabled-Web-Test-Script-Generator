# Test Data Requirements

- Flow name: Log in as a customer and search for an in stock product

## validCustomerUser

- Type: `user`
- Required: `True`
- Required fields: `username, password, role`
- Data constraints: `{'role': 'customer', 'status': 'active'}`
- Preferred sources: `inline, env, json, database, api`
- Synthetic data allowed: `False`
- Classification: `existing_qa_data_required`
- Why: A valid existing QA user is required before browser exploration.

## inStockProduct

- Type: `product`
- Required: `True`
- Required fields: `sku, name, searchTerm`
- Data constraints: `{'status': 'inStock'}`
- Preferred sources: `inline, json, csv, database, api`
- Synthetic data allowed: `False`
- Classification: `existing_qa_data_required`
- Why: The flow needs a valid in-stock product to avoid random search data.
