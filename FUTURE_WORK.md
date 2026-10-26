# Future work

- **Month indicator on the cards:** replace the outlined cells and the highlighted letter with one highlighted column that runs through the whole calendar card, so the current month reads at a glance.
- **Remove `frontend/src/register.ts`:** it should not be necessary. Home Assistant loads extra modules with a bare `import()`, and when our small bundle won that race its elements were registered too early and showed up as "Configuration error" cards, so registration now waits for the `home-assistant` element. The `home-assistant-notes` project no longer has this problem since its Bronze quality-scale work. Compare how it loads and registers its card, and check the Bronze requirements for a proper fix, then drop the workaround.
- **Logo text is cut off:** in the large logo (`custom_components/seasonal_groceries/brand/logo@2x.png`) the text stops at "Groci". The generated SVG is too narrow for "Seasonal Groceries" at that font size; widen the canvas or shrink the text, then regenerate `logo.png` and `logo@2x.png`.
- **Run the PyCharm MCP to fix issues:** connect to the PyCharm MCP server and use its inspections (file problems, lint) over the whole project, then fix what it reports in addition to ruff and the TypeScript typecheck. The PyCharm MCP server failed to connect in this session, so check that it is running before relying on it.
- Judgment calls and deferrals
- Fuzzy matches and "No season" in the score: unconfirmed fuzzy matches still count toward a recipe's score, and "No season" still counts in the total. Both follow your design, and I left them as they were.
- Deferred as minor:
  - The match card keeps item names in the old language after a language change until you reload.
  - Credit URLs have no https? check.
  - A duplicate ingredient in one recipe counts twice.
- Mealie card seperate
- Each custom card its own card.ts?