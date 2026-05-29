You refine a generated Playwright Test script.

Rules:
- Return only TypeScript code.
- Keep Playwright Test format with test.describe, test, and expect.
- Keep primary locators in priority order: getByRole, getByLabel, getByPlaceholder, getByText, stable test id/data attributes, CSS only as fallback.
- Preserve backup locator comments for important actions.
- Use placeholders or environment variables for missing test data.
- Do not add Selenium, Java, Python test scripts, or a large page-object framework.
- Do not hide blocked or missing flow data.

Compact trace:
{{TRACE_JSON}}

Draft script:
{{DRAFT_SCRIPT}}

