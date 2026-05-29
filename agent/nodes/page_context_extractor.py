from __future__ import annotations

from typing import Any

from agent.state import PageContext
from agent.utils.token_budget import compact_text


MAX_ITEMS = 30


async def extract_page_context(page) -> PageContext:
    """Return compact, reviewable page context without serializing full HTML."""
    data = await page.evaluate(
        """
        () => {
          const visible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none'
              && rect.width > 0 && rect.height > 0;
          };
          const text = (el) => (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
          const labelFor = (el) => {
            if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
            if (el.id) {
              const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
              if (label && label.innerText.trim()) return label.innerText.trim();
            }
            const parentLabel = el.closest('label');
            if (parentLabel && parentLabel.innerText.trim()) return parentLabel.innerText.trim();
            return '';
          };
          const testSelector = (el) => {
            for (const attr of ['data-testid', 'data-test', 'data-cy', 'data-qa']) {
              const value = el.getAttribute(attr);
              if (value) return `[${attr}="${CSS.escape(value)}"]`;
            }
            if (el.id) return `#${CSS.escape(el.id)}`;
            if (el.name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
            return '';
          };
          const limit = (items) => items.filter(Boolean).filter((item) => item.text || item.label || item.placeholder || item.name).slice(0, 30);
          const buttons = limit([...document.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"],input[type="reset"]')]
            .filter(visible)
            .map((el) => ({ text: text(el), role: 'button', selector: testSelector(el), type: el.type || '' })));
          const links = limit([...document.querySelectorAll('a[href],[role="link"]')]
            .filter(visible)
            .map((el) => ({ text: text(el), role: 'link', href: el.href || '', selector: testSelector(el) })));
          const inputs = limit([...document.querySelectorAll('input,textarea,select')]
            .filter(visible)
            .map((el) => ({
              label: labelFor(el),
              placeholder: el.getAttribute('placeholder') || '',
              name: el.getAttribute('name') || '',
              type: el.getAttribute('type') || el.tagName.toLowerCase(),
              role: el.getAttribute('role') || '',
              selector: testSelector(el),
              value: el.value || ''
            })));
          const roles = limit([...document.querySelectorAll('[role]')]
            .filter(visible)
            .map((el) => ({ role: el.getAttribute('role'), text: text(el), selector: testSelector(el) })));
          const errors = [...document.querySelectorAll('[role="alert"],.error,.alert,[aria-invalid="true"]')]
            .filter(visible)
            .map((el) => text(el))
            .filter(Boolean)
            .slice(0, 10);
          return { buttons, links, inputs, roles, errors };
        }
        """
    )
    return {
        "url": page.url,
        "title": compact_text(await page.title(), 120),
        "buttons": data.get("buttons", [])[:MAX_ITEMS],
        "links": data.get("links", [])[:MAX_ITEMS],
        "inputs": data.get("inputs", [])[:MAX_ITEMS],
        "roles": data.get("roles", [])[:MAX_ITEMS],
        "errors": [compact_text(item, 180) for item in data.get("errors", [])[:10]],
    }

