# CLAUDE.md - Project Guidelines

## gstack

Use the /browse skill from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.

### Available Skills

- `/office-hours` - Office hours mode
- `/plan-ceo-review` - Founder/CEO mode: Rethink the problem, find the 10-star product
- `/plan-eng-review` - Eng manager/tech lead mode: Lock in architecture, data flow, diagrams, edge cases
- `/plan-design-review` - Senior product designer mode: Designer's eye audit, 80-item checklist, AI Slop detection
- `/design-consultation` - Design consultant mode: Build complete design system from scratch
- `/review` - Paranoid staff engineer mode: Find bugs that pass CI but blow up in production
- `/ship` - Release engineer mode: Sync main, run tests, review diff, bump version, commit, push, create PR
- `/browse` - QA engineer mode: Browser automation, screenshots, console checks
- `/qa` - QA + fix engineer mode: Test app, find bugs, fix with atomic commits
- `/qa-only` - QA reporter mode: Report-only QA testing, never fixes
- `/design-review` - Design audit mode
- `/setup-browser-cookies` - Session manager mode: Import cookies from real browser
- `/retro` - Engineering manager mode: Team-aware retrospective with per-person praise
- `/investigate` - Debug and investigate errors
- `/document-release` - Technical writer mode: Update README, ARCHITECTURE, CONTRIBUTING, project docs
- `/codex` - Second opinion / adversarial code review
- `/careful` - Extra caution mode for production systems
- `/freeze` - Scope edits to one module/directory
- `/guard` - Maximum safety mode (destructive warnings + edit restrictions)
- `/unfreeze` - Remove edit restrictions
- `/gstack-upgrade` - Upgrade gstack to latest version

## Care Philosophy

Always read `docs/philosophy.md` before writing patient-facing features. The core principle: **help the patient be known**. Every interaction should make the patient feel known, not processed.

Key rules:
- **Never** use "contact your care team" as a brush-off — Clintela IS the care team
- **Always** use warm, conversational language — the language of the home, not the institution
- **Always** reference patient preferences/goals/concerns when available
- **Never** over-medicalize — inform choices, don't impose treatments
- **Test:** "Would this interaction make the patient feel known, or processed?"

## Design System

Always read DESIGN.md before making any visual or UI decisions. All font choices (Satoshi), colors (Teal/Coral/Purple), spacing, and aesthetic direction are defined there. Do not deviate without explicit user approval.

Key principles:
- **Typography:** Satoshi font family, tight tracking on headlines only (never lowercase)
- **Color:** Confident palette — Teal (#0D9488) primary, Coral (#EA580C) accent, Purple (#7C3AED) secondary
- **Spacing:** 4px base unit, generous for patients, compact for clinicians
- **Accessibility:** WCAG 2.1 AA minimum, 16px text minimum, 44px touch targets
- **Dark mode:** First-class citizen, essential for night-shift clinicians

In QA mode, flag any code that doesn't match DESIGN.md.
