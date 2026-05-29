You are analyzing a user-provided web automation flow.

Return only JSON. Do not include Markdown.

Input flow:
{{FLOW}}

Create a compact ordered list of steps. Use these intent values only:
fill, click, select, check, uncheck, submit, assert.

Schema:
{
  "steps": [
    {
      "text": "short user-visible step",
      "intent": "click",
      "keywords": ["important", "matching", "words"]
    }
  ]
}

Do not invent credentials, OTPs, CAPTCHA answers, or hidden navigation.

