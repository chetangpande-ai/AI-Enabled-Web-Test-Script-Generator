# Web Crawler Test Generation Agent

Minimal LangGraph agent that explores a focused user flow with Playwright and generates reviewable Playwright Test scripts in TypeScript.

## What It Does

- Accepts an application URL, high-level flow, optional test data, and optional constraints.
- Opens the target app with Python Playwright.
- Extracts compact page context instead of full HTML.
- Follows deterministic, flow-relevant controls instead of crawling the whole app.
- Generates `generated-tests/tests/generated-flow.spec.ts` in Playwright Test style.
- Writes HITL review metadata and reports.
- Runs only configured validation commands.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install
```

Install generated test dependencies:

```bash
cd generated-tests
npm install
npx playwright install
```

Optional LLM refinement uses LangChain with OpenAI:

```bash
set OPENAI_API_KEY=your_key
set CRAWLER_AGENT_MODEL=gpt-4o-mini
```

Without `OPENAI_API_KEY`, the agent uses deterministic parsing and script generation.

## Run

```bash
python -m agent run ^
  --url "https://your-app.example" ^
  --flow "Log in with valid credentials, open billing, verify the invoice list is visible" ^
  --test-data "{\"username\":\"user@example.com\",\"password\":\"secret\"}" ^
  --constraints "{\"browser\":\"chromium\",\"headless\":true,\"pages_to_avoid\":[\"logout\",\"delete\"]}"
```

Use environment variables or placeholders for sensitive data. Do not hardcode real credentials in generated tests.

## HITL Review

After each run, inspect:

- `generated-tests/tests/generated-flow.spec.ts`
- `reports/exploration_summary.md`
- `reports/missing_info.md`
- `reports/validation_report.md`
- `reports/hitl_review.json`

Record review decisions:

```bash
python -m agent review --decision approve --notes "Reviewed and accepted"
python -m agent review --decision reject --notes "Wrong page was selected"
python -m agent review --decision changes --notes "Use email field before password"
```

If rejected or changes are requested, rerun the agent with clearer flow text or additional test data. The agent updates generated scripts and report metadata only.

## Validation

The validator runs commands that are configured in `generated-tests/package.json`:

- `npm install`
- `npm run install:browsers`
- `npm run test:list`
- `npm run typecheck`
- `npm test`, only when `--run-tests` is supplied and no missing information was reported

If validation fails, fix only issues caused by generated code and rerun. If validation is blocked by credentials, CAPTCHA, OTP, MFA, network access, or unclear steps, provide the missing information rather than bypassing security controls.

## Token Optimization

- The LLM is optional and only used for flow interpretation or final script refinement.
- Full HTML is never sent to the LLM.
- Page context is compacted to URL, title, visible buttons, links, inputs, ARIA roles, and error messages.
- Page summaries are cached by URL during a run.
- Deterministic scoring chooses actions whenever visible labels, roles, placeholders, and stable test IDs are sufficient.
