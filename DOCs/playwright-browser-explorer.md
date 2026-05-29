# Playwright Browser Explorer

The Playwright Browser Explorer performs focused browser exploration for the requested business flow.

Source files:

```text
agent/nodes/playwright_explorer.py
agent/nodes/page_context_extractor.py
agent/nodes/script_generator.py
generated-tests/playwright.config.ts
generated-tests/fixtures/test-data.fixture.ts
```

## Purpose

The explorer opens the target application, follows only flow-relevant controls, records successful actions, captures compact page context, and passes the action trace to the script generator.

It is not a full-site crawler.

## Entry Conditions

The explorer starts only after:

- Flow analysis has produced ordered steps.
- Test data requirements have been identified.
- Connectors have fetched candidate data.
- Resolver has produced `resolved_test_data`.
- Missing-data HITL has either resolved data or confirmed the flow is blocked/skipped.

If required data is missing, the explorer returns:

```json
{
  "exploration_status": "blocked",
  "explored_actions": [],
  "not_automated_flows": ["..."],
  "missing_info": ["Provide username, password, role for validCustomerUser."]
}
```

## Inputs

Example state consumed by the explorer:

```json
{
  "app_url": "https://qa.example.com",
  "constraints": {
    "browser": "chromium",
    "headless": true,
    "timeout_ms": 15000,
    "pages_to_avoid": ["logout", "delete"]
  },
  "analyzed_flow": [
    {
      "index": 1,
      "text": "Log in as a customer",
      "intent": "fill",
      "keywords": ["log", "customer"]
    }
  ],
  "resolved_test_data": {
    "resolvedData": {
      "user": {
        "username": "qa_customer_01",
        "password": "runtime-only",
        "role": "customer"
      }
    }
  }
}
```

## Supported Browser Constraints

Pass constraints with `--constraints`.

Example:

```bash
python -m agent run ^
  --url "https://qa.example.com" ^
  --flow "Log in and verify dashboard" ^
  --test-data "{\"user\":{\"username\":\"qa_customer_01\",\"password\":\"runtime-only\",\"role\":\"customer\",\"status\":\"active\"}}" ^
  --constraints "{\"browser\":\"chromium\",\"headless\":true,\"timeout_ms\":20000,\"pages_to_avoid\":[\"logout\",\"delete\"]}"
```

Supported fields:

| Field | Purpose | Example |
| --- | --- | --- |
| `browser` | Browser engine name | `chromium`, `firefox`, `webkit` |
| `headless` | Run without UI | `true` |
| `timeout_ms` | Initial navigation timeout | `15000` |
| `pages_to_avoid` | URL fragments to avoid | `["logout", "delete"]` |
| `avoid_pages` | Alias for `pages_to_avoid` | `["admin"]` |

## Exploration Strategy

The explorer uses deterministic matching:

1. Open `app_url`.
2. Extract compact page context.
3. Read the next flow step.
4. Score visible buttons, links, inputs, and form fields against step keywords.
5. Execute one relevant action.
6. Capture URL changes and assertion opportunities.
7. Stop when the flow completes or blocks.

It does not:

- Crawl every link.
- Randomly click controls.
- Invent values.
- Retry with random data after validation failure.
- Bypass OTP, CAPTCHA, MFA, or security controls.

## Page Context Extraction

The page context extractor captures compact browser state without sending full HTML to the LLM.

Captured fields:

```json
{
  "url": "https://qa.example.com/login",
  "title": "Login",
  "buttons": [
    {
      "text": "Sign in",
      "role": "button",
      "selector": "[data-testid=\"sign-in\"]"
    }
  ],
  "links": [
    {
      "text": "Forgot password",
      "href": "https://qa.example.com/forgot-password"
    }
  ],
  "inputs": [
    {
      "label": "Email",
      "placeholder": "name@example.com",
      "name": "email",
      "type": "email",
      "selector": "#email"
    }
  ],
  "roles": [
    {
      "role": "main",
      "text": "Login"
    }
  ],
  "errors": []
}
```

The cache is keyed by URL in `page_context_cache`.

## Supported Actions

| Intent | Browser action |
| --- | --- |
| `fill` | Fill matching input fields from resolved data |
| `click` | Click matching button or link |
| `select` | Select option using resolved data |
| `check` | Check checkbox or radio |
| `uncheck` | Uncheck checkbox |
| `submit` | Fill available fields, then click matching submit control |
| `assert` | Capture a text or URL assertion point |

## Data Mapping

Field labels, placeholders, names, and step text are mapped to resolved test data paths.

Examples:

| Field clue | Resolved data path |
| --- | --- |
| `email`, `username`, `login` | `testData.user.username` |
| `password`, `passcode` | `testData.user.password` |
| `search`, `query`, `keyword` | `testData.product.searchTerm` |
| `sku`, `product code` | `testData.product.sku` |
| `address`, `street`, `line1` | `testData.shippingAddress.line1` |
| `city` | `testData.shippingAddress.city` |
| `state`, `province` | `testData.shippingAddress.state` |
| `postal`, `zip`, `postcode` | `testData.shippingAddress.postalCode` |

Example action trace:

```json
{
  "step_index": 1,
  "step_text": "Enter username",
  "action": "fill",
  "value_key": "username",
  "value_path": "user.username",
  "target": "Email name@example.com email",
  "primary_locator": {
    "kind": "label",
    "label": "Email"
  },
  "backup_locators": [
    {
      "kind": "placeholder",
      "placeholder": "name@example.com"
    },
    {
      "kind": "css",
      "selector": "#email"
    }
  ],
  "status": "completed"
}
```

## Locator Priority

Generated scripts prefer locators in this order:

1. `getByRole`
2. `getByLabel`
3. `getByPlaceholder`
4. `getByText`
5. Stable `data-testid`, `data-test`, `data-cy`, or `data-qa`
6. CSS selector fallback

Example generated locator:

```ts
const target1 = page.getByLabel(/Email/i);
// Backup locators: page.getByPlaceholder(/name@example\.com/i); page.locator("#email")
await target1.fill(testData.user.username);
await expect(target1).toHaveValue(testData.user.username);
```

## Generated Test Output

Generated tests import from the test-data fixture:

```ts
import { test, expect } from '../fixtures/test-data.fixture';

test.describe('Generated web flow', () => {
  test('Log in as a customer and search for an in-stock product', async ({ page, testData }) => {
    await page.goto(process.env.BASE_URL ?? 'https://qa.example.com');
    await expect(page).not.toHaveURL('about:blank');

    const email = page.getByLabel(/email|username/i);
    await email.fill(testData.user.username);

    const password = page.getByLabel(/password/i);
    await password.fill(testData.user.password);

    await page.getByRole('button', { name: /login|sign in/i }).click();

    const search = page.getByPlaceholder(/search/i);
    await search.fill(testData.product.searchTerm);
    await page.getByRole('button', { name: /search/i }).click();

    await expect(page.getByText(testData.product.name)).toBeVisible();
  });
});
```

## Fixture

The fixture lives at:

```text
generated-tests/fixtures/test-data.fixture.ts
```

It reads:

```text
generated-tests/test-data/users.json
generated-tests/test-data/products.json
generated-tests/test-data/checkout-data.json
```

Example fixture usage:

```ts
import { test, expect } from '../fixtures/test-data.fixture';

test('uses resolved test data', async ({ page, testData }) => {
  await page.goto(process.env.BASE_URL ?? '');
  await page.getByLabel(/email/i).fill(testData.user.username);
  await page.getByLabel(/password/i).fill(testData.user.password);
  await expect(page.locator('body')).toBeVisible();
});
```

Secrets should come from environment variables:

```ts
password: process.env[user.passwordEnv] || process.env.QA_CUSTOMER_PASSWORD || ''
```

## Failure Handling

The explorer reports failures honestly.

Examples:

```text
Step 2 could not find a matching visible button or link.
Step 3 needs resolved test data path for 'password'.
Page reported error before step 4: Invalid credentials.
Exploration blocked: TimeoutError: page.goto timed out.
```

Blocked flows appear in:

```text
reports/exploration_summary.md
reports/missing_info.md
reports/missing_test_data.md
```

## HITL Interaction Points

### Missing-Data HITL

Runs before browser exploration.

```text
Test Data Resolver -> Missing-Data HITL Gate -> Browser Explorer
```

If missing data exists:

- Browser does not open.
- Exact missing fields are reported.
- User can provide data, skip, request synthetic data when allowed, change data source, or reject.

### Final Review HITL

Runs after validation.

The report includes:

- Generated script path
- Explored steps
- Assumptions
- Missing information
- Automated flows
- Flows not automated
- Validation status

## Validation Commands

Configured in:

```text
generated-tests/package.json
```

Commands:

```bash
cd generated-tests
npm install
npm run install:browsers
npm run test:list
npm run typecheck
npm test
```

The agent validator runs only configured commands. Full test execution is skipped when required data is missing unless explicitly requested and safe.

## Debugging Tips

Use headed mode:

```bash
python -m agent run ^
  --url "https://qa.example.com" ^
  --flow "Log in as a customer" ^
  --test-data "{\"user\":{\"username\":\"qa_customer_01\",\"password\":\"runtime-only\",\"role\":\"customer\",\"status\":\"active\"}}" ^
  --constraints "{\"headless\":false,\"browser\":\"chromium\"}"
```

Avoid destructive pages:

```json
{
  "pages_to_avoid": ["logout", "delete", "remove", "admin"]
}
```

Inspect generated artifacts:

```text
generated-tests/tests/generated-flow.spec.ts
reports/exploration_summary.md
reports/validation_report.md
```

## Safety Rules

- Do not bypass CAPTCHA, OTP, MFA, or restricted security controls.
- Do not use production data.
- Do not hardcode credentials.
- Do not print secrets.
- Do not continue after data validation failure.
- Do not hide blocked flows.
- Do not generate Selenium, Java, or Python final test scripts.

