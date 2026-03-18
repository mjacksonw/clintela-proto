# Design System — Clintela

**AI-powered post-surgical patient recovery support**

*Created: 2026-03-17*  
*For: Patients, Clinicians, and Healthcare Administrators*

---

## Product Context

**What this is:** Clintela is a multi-agent AI system that provides 24/7 care coordination for patients recovering from surgery. It bridges the gap between hospital discharge and full recovery, helping prevent preventable readmissions through continuous monitoring, intelligent triage, and seamless escalation to human clinicians.

**Who it's for:**
- **Patients:** Often elderly, recovering from surgery, potentially anxious or in pain. Need reassurance, clarity, and simplicity.
- **Clinicians:** Nurses and physicians managing large patient panels. Need efficiency, quick scanning, and clear prioritization.
- **Administrators:** Hospital leadership tracking outcomes and quality metrics. Need authoritative data presentation.

**Space/Industry:** Healthcare technology — post-acute care, patient engagement, clinical workflow

**Project type:** Multi-interface web application (patient SMS/web, clinician dashboard, admin analytics)

**Core Design Challenge:** Create a system that feels warm and approachable for anxious patients while being efficient and authoritative for time-pressed clinicians. The same brand, two very different contexts.

---

## Design Philosophy

### Core Principles

1. **Clarity over cleverness** — In healthcare, confusion can be dangerous. Every interaction should be immediately understandable.

2. **Reassurance through design** — Patients may be worried. The interface should feel calm, supportive, and never alarming unless truly urgent.

3. **Efficiency for clinicians** — Time is critical in clinical settings. Information should be scannable, actions should be one-click, and the system should surface what matters.

4. **Accessibility is non-negotiable** — WCAG 2.1 AA minimum. Many users are elderly or may be using the system while not feeling well.

5. **Multi-modal consistency** — The experience should feel cohesive whether the patient is texting, on the web, or talking to a voice agent.

---

## Aesthetic Direction

**Direction:** Confidently Human

**Decoration level:** Intentional — Clean and trustworthy with confident warmth through bold, expert use of color

**Mood:** The design should feel like a skilled nurse: competent, caring, and calm under pressure. Not sterile like a hospital, not playful like a consumer app, but confidently human. The color says "we know what we're doing" while the typography and spacing say "we care about you."

**Visual Metaphor:** A well-designed hospital room — functional, clean, but with warm lighting and comfortable textures that put patients at ease.

---

## Typography

### Font Strategy

We need two distinct typographic voices:

**For Patients (SMS, Web Chat, Patient Portal):**
- Warm, approachable, highly readable
- Generous sizing for elderly users
- Clear hierarchy without feeling clinical
- Personality without sacrificing accessibility

**For Clinicians (Dashboard, Admin):**
- Efficient, scannable, information-dense
- Tabular numbers for data
- Clear hierarchy for quick decision-making
- Professional but not cold

### Font Selections

**Primary Font Family: Satoshi**

Satoshi is a modern geometric sans-serif with personality. It feels contemporary and designed, not default. Excellent readability at all sizes with character that makes the interface feel intentionally crafted.

- **Loading:** Google Fonts or self-hosted (https://www.fontshare.com/fonts/satoshi)
- **Weights used:** 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold)
- **Why Satoshi:** Has the personality to carry our bold color palette while maintaining excellent readability

**Display/Headlines: Satoshi (same family)**

Let the typeface do the work. Satoshi at larger sizes with tight letterspacing (tracking: -0.02em) creates clear hierarchy and confident presence.

**Data/Tables: Satoshi with tabular-nums**

```css
font-variant-numeric: tabular-nums;
```

This ensures numbers align in tables (vital for clinical data like blood pressure readings, medication dosages).

**Monospace (for code, technical IDs): JetBrains Mono**

Clean, readable monospace for any technical content or system-generated IDs.

### Type Scale

Using a 1.25 (Major Third) modular scale for clear hierarchy:

| Level | Size | Usage |
|-------|------|-------|
| Hero | 48px / 3rem | Landing page headlines |
| H1 | 40px / 2.5rem | Page titles |
| H2 | 32px / 2rem | Section headers |
| H3 | 25.6px / 1.6rem | Card titles |
| H4 | 20.8px / 1.3rem | Subsection headers |
| Body Large | 18px / 1.125rem | Patient messages, important text |
| Body | 16px / 1rem | Default body text |
| Body Small | 14px / 0.875rem | Captions, metadata |
| Label | 12px / 0.75rem | Form labels, badges |

**Patient Interface Minimums:**
- Body text: 16px minimum (18px preferred)
- Buttons: 18px minimum
- Line height: 1.6 for body text (more breathing room)

**Clinician Interface:**
- Body text: 14px acceptable (dense information)
- Line height: 1.5 for efficiency
- Tabular data: 13px with tabular-nums

### Typography Rules

- **Never use light font weights (< 400)** — Accessibility concern, especially for elderly users
- **Headings use semibold (600), not bold** — Less aggressive, more refined
- **Patient messages: 18px, line-height 1.6** — Easy reading for potentially tired/anxious users
- **Clinician dashboard: 14px base, compact spacing** — Information density
- **Always left-align text** — Centered text is harder to read, especially for elderly users
- **Maximum line length: 75 characters** — Prevent eye strain
- **Letter-spacing: Tight tracking (-0.02em) for headlines only** — Creates confident, modern feel
- **Never letterspace lowercase** — "Any man who would letterspace lowercase would steal sheep" — Frederic Goudy
- **Uppercase text: Use sparingly, with generous letter-spacing (0.05em)** — Labels, badges, buttons

---

## Color

### Color Philosophy

Healthcare color systems must balance several needs:
- **Trust and confidence** (patients need reassurance)
- **Urgency and clarity** (clinicians need to spot problems)
- **Accessibility** (color blindness is common, especially in older populations)

We use a **confident** color approach — bold and intentional, not afraid of color like most healthcare apps. The palette says "we know what we're doing" while remaining professional and trustworthy. Semantic colors are reserved for their specific meanings.

### Primary Palette

**Primary Blue: #2563EB**
- Usage: Primary actions, links, brand identity
- Rationale: Trustworthy, professional, accessible (WCAG AA on white)
- Dark mode: #3B82F6 (slightly brighter for dark backgrounds)

**Secondary Teal: #0D9488**
- Usage: Secondary actions, accents, success states
- Rationale: Healthcare-adjacent without being clinical cold
- Dark mode: #14B8A6

### Neutrals

Warm gray scale (slightly warm undertones feel more human than pure neutral):

| Token | Hex | Usage |
|-------|-----|-------|
| Gray 50 | #FAFAF9 | Page backgrounds (subtle warmth) |
| Gray 100 | #F5F5F4 | Card backgrounds |
| Gray 200 | #E7E5E4 | Borders, dividers |
| Gray 300 | #D6D3D1 | Disabled states |
| Gray 400 | #A8A29E | Placeholder text |
| Gray 500 | #78716C | Secondary text |
| Gray 600 | #57534E | Body text (light mode) |
| Gray 700 | #44403C | Headings (light mode) |
| Gray 800 | #292524 | High contrast text |
| Gray 900 | #1C1917 | Near-black |

### Semantic Colors (Reserved Meanings)

These colors have specific meanings and should not be used for branding or decoration:

**Success: #059669**
- Meaning: Recovery on track, task completed, positive outcome
- Usage: Green status indicators, success messages, completion badges

**Warning: #D97706**
- Meaning: Attention needed, but not urgent
- Usage: Yellow/amber status, upcoming deadlines, mild symptoms

**Danger: #DC2626**
- Meaning: Urgent attention required
- Usage: Red status, critical symptoms, escalation needed

**Info: #2563EB**
- Meaning: Neutral information, guidance
- Usage: Tips, educational content, system messages

### Triage Status Colors (Clinician Dashboard)

The triage view uses a specific color system for patient severity:

| Status | Color | Hex | Meaning |
|--------|-------|-----|---------|
| Green | Success Green | #059669 | Stable, on track |
| Yellow | Warning Amber | #D97706 | Notice, mild concern |
| Orange | Warning Dark | #EA580C | Warning, needs attention |
| Red | Danger Red | #DC2626 | Critical, immediate action |

**Important:** These colors must work for colorblind users. Always pair with:
- Icons (checkmark, alert triangle, etc.)
- Text labels ("Stable", "Warning", "Critical")
- Position (red/orange at top of list)

### Dark Mode

Dark mode is **essential** for clinicians working night shifts.

**Strategy:** Redesign surfaces, don't just invert

- **Background:** #0F172A (deep slate, not pure black — easier on eyes)
- **Surface:** #1E293B (elevated cards, panels)
- **Border:** #334155 (subtle separation)
- **Text Primary:** #F8FAFC (off-white, not pure white)
- **Text Secondary:** #94A3B8 (muted for hierarchy)

**Color adjustments in dark mode:**
- Primary blue: Saturate 10% lighter (#3B82F6)
- Semantic colors: Keep similar hue, adjust lightness for contrast
- Never use pure black (#000000) — causes eye strain

---

## Spacing

### Base Unit: 4px

All spacing is based on multiples of 4px for consistency and alignment.

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| space-1 | 4px | Tight padding, icon gaps |
| space-2 | 8px | Button padding (vertical), small gaps |
| space-3 | 12px | Compact card padding |
| space-4 | 16px | Standard padding, form field gaps |
| space-5 | 20px | Medium gaps |
| space-6 | 24px | Section padding, card padding |
| space-8 | 32px | Large section gaps |
| space-10 | 40px | Page-level spacing |
| space-12 | 48px | Major section breaks |
| space-16 | 64px | Hero sections |

### Spacing Rules

**Patient Interface:**
- Generous spacing (relaxed, approachable)
- Card padding: 24px (space-6)
- Section gaps: 32px (space-8)
- Touch targets: Minimum 44px height

**Clinician Interface:**
- Compact spacing (efficient, scannable)
- Card padding: 16px (space-4)
- Table row height: 48px (clickable, but dense)
- Section gaps: 16px (space-4)

**Density Modes:**
Consider offering density toggle for clinician dashboard:
- **Comfortable:** Default, balanced
- **Compact:** More information visible, for power users

---

## Layout

### Layout Approach: Grid-Disciplined

Healthcare interfaces need predictability. Users should know where to find information without hunting.

### Grid System

**12-column grid** for all layouts:
- Column width: Flexible
- Gutter: 24px (desktop), 16px (tablet), 12px (mobile)
- Margin: 24px (desktop), 16px (tablet), 12px (mobile)

### Breakpoints

| Breakpoint | Width | Target |
|------------|-------|--------|
| Mobile | 0-639px | Patient SMS fallback, mobile web |
| Tablet | 640-1023px | Tablets, small laptops |
| Desktop | 1024-1439px | Standard monitors |
| Wide | 1440px+ | Large monitors, dashboards |

### Max Content Width

- **Patient pages:** 720px (comfortable reading width)
- **Clinician dashboard:** 1440px (full data visibility)
- **Admin analytics:** 1200px (charts and metrics)

### Layout Patterns

**Patient Interface:**
- Single column, centered content
- Large touch targets
- Clear visual hierarchy with generous whitespace
- Sticky header with progress indicator (recovery timeline)

**Clinician Dashboard:**
- Sidebar navigation (collapsible)
- Main content area with card-based layout
- Triage list prioritized by severity (red/orange/yellow/green)
- Right panel for patient details (when selected)

**Admin Interface:**
- Top navigation with dropdown menus
- Grid of metric cards
- Full-width charts
- Filter bar above data tables

---

## Components

### Buttons

**Primary Button:**
- Background: Primary Blue (#2563EB)
- Text: White
- Padding: 12px 24px (space-3 space-6)
- Border radius: 6px
- Font: 16px, semibold (600)
- Hover: Darken 10%, subtle shadow
- Active: Darken 15%
- Disabled: Gray 300 background, Gray 500 text

**Secondary Button:**
- Background: White (or transparent in dark mode)
- Border: 1px solid Gray 300
- Text: Gray 700
- Same sizing as primary

**Danger Button:**
- Background: Danger Red (#DC2626)
- Text: White
- Use only for destructive actions (delete, remove)

**Button States:**
- Default → Hover → Active → Loading → Disabled
- Loading: Spinner + "Loading..." text
- Always show state changes immediately

### Cards

**Patient Card:**
- Background: White (or Gray 800 in dark mode)
- Border: 1px solid Gray 200
- Border radius: 8px
- Padding: 24px
- Shadow: 0 1px 3px rgba(0,0,0,0.1)
- Hover: Subtle lift (shadow increases)

**Clinician Patient Card (Triage):**
- Compact: 16px padding
- Left border: 4px solid (color-coded by status)
- Status badge in top-right
- One-click actions visible on hover

### Forms

**Input Fields:**
- Height: 48px (touch-friendly)
- Border: 1px solid Gray 300
- Border radius: 6px
- Padding: 12px 16px
- Font: 16px (prevents iOS zoom)
- Focus: Primary blue border, subtle glow
- Error: Danger red border, error message below

**Labels:**
- Font: 14px, medium (500)
- Color: Gray 700
- Margin bottom: 8px
- Required indicator: Red asterisk

**Helper Text:**
- Font: 14px
- Color: Gray 500
- Margin top: 4px

### Status Badges

| Type | Background | Text | Usage |
|------|------------|------|-------|
| Success | #D1FAE5 | #065F46 | Recovered, on track |
| Warning | #FEF3C7 | #92400E | Mild concern, watch |
| Danger | #FEE2E2 | #991B1B | Critical, action needed |
| Info | #DBEAFE | #1E40AF | Informational |
| Neutral | #F5F5F4 | #44403C | Default, pending |

### Alerts

**Alert Banner:**
- Full width within container
- Padding: 16px
- Icon + text layout
- Dismissible (X button on right)
- Colors match badge system

**Toast Notifications:**
- Position: Top-right (desktop), top-center (mobile)
- Auto-dismiss: 5 seconds
- Manual dismiss: X button
- Stacking: Up to 3, newest on top

---

## Motion

### Motion Philosophy

Motion should be **functional, not decorative**. Every animation should communicate something:
- State change (loading, success, error)
- Spatial relationship (where did that come from?)
- Attention direction (look here)

### Motion Approach: Intentional

Subtle, purposeful motion that aids comprehension without drawing attention to itself.

### Easing Functions

- **Enter:** `ease-out` (decelerate — feels responsive)
- **Exit:** `ease-in` (accelerate — feels like it's leaving)
- **Move:** `ease-in-out` (smooth, balanced)

### Duration Scale

| Type | Duration | Usage |
|------|----------|-------|
| Micro | 50-100ms | Button states, checkbox ticks |
| Short | 150-250ms | Hover effects, small transitions |
| Medium | 250-400ms | Card expansions, panel slides |
| Long | 400-700ms | Page transitions, major reveals |

### Specific Animations

**Button Hover:**
- Transform: translateY(-1px)
- Shadow: Increase depth
- Duration: 150ms
- Easing: ease-out

**Card Hover:**
- Transform: translateY(-2px)
- Shadow: Increase from sm to md
- Duration: 200ms

**Page Load:**
- Content fades in (opacity 0 → 1)
- Slight upward movement (translateY 10px → 0)
- Duration: 400ms
- Stagger: 50ms between sections

**Loading States:**
- Skeleton screens (not spinners) for content
- Shimmer animation on skeleton
- Duration: 1.5s, infinite loop

**Real-time Updates (Clinician Dashboard):**
- New patient slides in from top
- Duration: 300ms
- Existing items shift down smoothly
- Color flash on status change (yellow → red)

### Accessibility

**Respect prefers-reduced-motion:**

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Accessibility

### WCAG 2.1 AA Compliance

**Non-negotiable requirements:**

1. **Color Contrast:**
   - Body text: 4.5:1 minimum
   - Large text (18px+): 3:1 minimum
   - UI components: 3:1 minimum

2. **Focus Indicators:**
   - All interactive elements have visible focus state
   - Focus ring: 2px solid Primary Blue, 2px offset
   - Never remove focus outlines without replacement

3. **Touch Targets:**
   - Minimum 44x44px for all interactive elements
   - Minimum 8px spacing between touch targets

4. **Text Sizing:**
   - Patient interface: 16px minimum
   - Browser zoom to 200% must not break layout

5. **Screen Readers:**
   - Semantic HTML (proper heading hierarchy)
   - ARIA labels where needed
   - Alt text for all images
   - Status announcements for dynamic content

6. **Color Independence:**
   - Never rely on color alone (always pair with icon or text)
   - Triage status: Color + icon + text label

### Patient-Specific Accessibility

- **Large text mode:** Option to increase base font size to 18px
- **High contrast mode:** For low vision users
- **Simplified language:** Avoid medical jargon in patient-facing text
- **Clear error messages:** "Please enter your date of birth" not "Invalid input"

---

## Multi-Modal Considerations

### SMS/Text Interface

- **Character limits:** Keep messages under 160 characters when possible
- **Clear structure:** Use line breaks, emojis sparingly for warmth
- **Action prompts:** End with clear next step ("Reply YES to confirm")
- **No markdown:** Plain text only, use formatting sparingly

### Voice Interface

- **Conversational tone:** Natural language, not robotic
- **Confirmation:** Repeat back critical information
- **Barge-in:** Allow users to interrupt
- **Error recovery:** Graceful handling of misheard inputs

### Web Interface

- **Progressive enhancement:** Core functionality works without JavaScript
- **Responsive:** Works on all device sizes
- **Offline awareness:** Clear messaging when connection is lost

---

## Dark Mode

### Implementation Strategy

Use CSS custom properties for easy theme switching:

```css
:root {
  --color-bg: #FAFAF9;
  --color-surface: #FFFFFF;
  --color-text: #44403C;
  --color-text-secondary: #78716C;
  --color-border: #E7E5E4;
  --color-primary: #2563EB;
}

[data-theme="dark"] {
  --color-bg: #0F172A;
  --color-surface: #1E293B;
  --color-text: #F8FAFC;
  --color-text-secondary: #94A3B8;
  --color-border: #334155;
  --color-primary: #3B82F6;
}
```

### Auto-Detection

Respect system preference:

```javascript
if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.documentElement.setAttribute('data-theme', 'dark');
}
```

### Manual Toggle

Provide toggle in settings for clinicians who prefer opposite of system setting.

---

## Implementation Notes

### CSS Architecture

- **Utility-first:** Use Tailwind CSS or similar for rapid development
- **Component library:** Build reusable components (Django templates + HTMX)
- **CSS variables:** For theming (light/dark mode)
- **No inline styles:** Maintain separation of concerns

### Iconography

- **Library:** Lucide icons (clean, consistent, accessible)
- **Sizing:** 16px (sm), 20px (md), 24px (lg), 32px (xl)
- **Stroke width:** 2px consistent
- **Color:** Inherit from text color

### Image Guidelines

- **Patient photos:** Optional, respectful, diverse representation
- **Illustrations:** Warm, human, not overly clinical
- **Icons:** Simple, clear, universally understood
- **Compression:** WebP format, lazy loading

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-17 | Initial design system created | Collaborative design consultation based on healthcare context and user needs |
| 2026-03-17 | **Satoshi as primary font** | Modern geometric sans with personality; carries bold color palette while maintaining excellent readability |
| 2026-03-17 | **Confident color palette** (Teal/Coral/Purple) | Bold, intentional use of color differentiates from typical healthcare apps; teal = confidence, coral = warmth, purple = sophistication |
| 2026-03-17 | **Warm gray neutral palette** | Feels more human than pure grays; appropriate for healthcare while maintaining professionalism |
| 2026-03-17 | **4px base spacing unit** | Aligns with most design systems, easy to calculate, supports both generous (patient) and compact (clinician) densities |
| 2026-03-17 | **Intentional motion approach** | Functional animations only; respects user attention and accessibility requirements |
| 2026-03-17 | **Dark mode as first-class** | Essential for clinicians working night shifts; designed as core feature, not afterthought |
| 2026-03-17 | **Tight letterspacing on headlines** | Creates confident, modern feel; never applied to lowercase (per Goudy's wisdom) |

---

## Related Documents

- [Clintela Foundation Design](./docs/designs/clintela-foundation.md) — Product vision and scope
- [Engineering Review](./docs/engineering-review.md) — Architecture and implementation
- [README](./README.md) — Project overview

---

*Clintela Design System — Warmly Professional, Accessible by Design*
