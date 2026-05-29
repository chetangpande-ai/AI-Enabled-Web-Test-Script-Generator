# Agent Documentation

This folder documents the production behavior of the Web Crawler Test Generation Agent.

## Contents

- [Test Data Requirements](test-data-requirements.md)
- [Test Data Connectors and Resolver](test-data-connectors.md)
- [Playwright Browser Explorer](playwright-browser-explorer.md)

## Workflow Summary

```text
User Input
  -> Flow Analyzer
  -> Test Data Requirement Node
  -> Test Data Connector Node
  -> Test Data Resolver Node
  -> Missing-Data HITL Gate
  -> Playwright Browser Explorer
  -> Page Context Extractor
  -> Script Generator
  -> Validation
  -> Final HITL Review
```

The browser explorer starts only after required test data is resolved, skipped by a human, or blocked and reported. It does not invent random data.

