# Plan: Path-based URL Routing for Clinician Dashboard

**Date:** 2026-03-24
**Branch:** claude/suspicious-taussig
**Status:** Eng review CLEARED — ready to implement

## Context

The clinician dashboard (`/clinician/dashboard/`) is an Alpine.js + HTMX SPA where patient selection, tab switches, and drill-down views (e.g., survey results) all happen without updating the browser URL. This means:
- **Back button doesn't work** — pressing Back leaves the dashboard entirely instead of returning to the previous view
- **No deep linking** — can't bookmark or share a link to a specific patient/tab
- **No navigation back from sub-views** — e.g., viewing survey results has no way to return to the Surveys tab
- **Surveys tab is unreachable** — the tab button is missing from the template (only accessible via keyboard shortcut `4`)

Patient and admin interfaces use full page loads and work correctly. This change is scoped to the clinician dashboard only.

## Approach: Path-based URL Routing with History API

Use real URL paths with `history.pushState()` to encode dashboard state. Requires minor server-side additions (URL patterns + view parameters) but gives clean, semantic URLs.

### URL Schema
```
/clinician/dashboard/                                           # No patient selected
/clinician/dashboard/patient/42/                                # Patient 42, Details tab (default)
/clinician/dashboard/patient/42/details/                        # Patient 42, Details tab
/clinician/dashboard/patient/42/surveys/                        # Patient 42, Surveys tab
/clinician/dashboard/patient/42/surveys/abc123-uuid/            # Survey result detail
/clinician/dashboard/patient/42/vitals/                         # Patient 42, Vitals tab
```

### History Behavior
- **Patient selection** → `pushState` (new history entry)
- **Tab switch** within same patient → `pushState` (new history entry)
- **Survey result drill-down** → `pushState` (new entry, so Back returns to surveys list)
- **Escape/deselect** → `pushState` to `/clinician/dashboard/`
- **Back from first view** → deselects patient (empty state), another Back leaves dashboard

### Error Handling
- Invalid/nonexistent patient ID in URL → server validates, returns dashboard with empty state
- Malformed URL → Django 404 (URL pattern doesn't match)
- Unauthorized patient → server validates access, returns dashboard with empty state

### Data Flow
```
  User clicks tab          User presses Back
       │                        │
       ▼                        ▼
  switchTab(tab)           popstate event
       │                        │
       ├─► _loadTab()           ├─► _restoreFromUrl()
       │   (HTMX ajax)         │   ├─► parse pathname
       │                        │   ├─► set Alpine state
       └─► _updateUrl()        │   ├─► _loadTab()
            (pushState)         │   └─► _loadChat()
                                │
                                └─► if base path: deselect patient
```

## Commits

### Commit 1: Fix missing Surveys tab button (standalone bug fix)
- `templates/base_clinician.html` — Add Surveys tab button between Research and Tools
- `templates/clinicians/components/_keyboard_help.html` — Update shortcuts to show 1-6

### Commit 2: Add path-based URL routing
**Server-side:**
- `apps/clinicians/urls.py` — Add URL patterns for dashboard with patient/tab/subview segments
- `apps/clinicians/views.py` — Modify `dashboard_view` to accept optional `patient_id`, `tab`, `subview` kwargs, pass to template context

**Client-side:**
- `static/js/clinician-dashboard.js` — Core routing logic (pushState, popstate, URL parsing)
- `templates/base_clinician.html` — Add data attributes for initial state from server
- `templates/clinicians/components/_patient_list_item.html` — Add `data-patient-id` attribute
- `templates/surveys/_tab_surveys.html` — Add `@click` handler to View links
- `templates/surveys/_survey_results.html` — Add "Back to Surveys" button

### Commit 3: Tests
- Django view tests (dashboard with path params, Surveys tab renders)
- Playwright E2E test: select patient → verify URL, switch tabs → verify URL, Back button, deep link, survey drill-down

## File Changes Detail

### 1. `apps/clinicians/urls.py` — New URL patterns

Add after existing dashboard path (line 14):
```python
# Dashboard with deep-link routing
path(
    "dashboard/patient/<int:patient_id>/",
    views.dashboard_view,
    name="dashboard_patient",
),
path(
    "dashboard/patient/<int:patient_id>/<str:tab>/",
    views.dashboard_view,
    name="dashboard_patient_tab",
),
path(
    "dashboard/patient/<int:patient_id>/<str:tab>/<str:subview>/",
    views.dashboard_view,
    name="dashboard_patient_tab_subview",
),
```

### 2. `apps/clinicians/views.py` — Accept optional path params

Modify `dashboard_view` signature and add initial state to context:
```python
def dashboard_view(request, patient_id=None, tab=None, subview=None):
    """Main three-panel dashboard."""
    clinician = request.clinician

    # Validate initial state from URL path
    initial_patient_id = None
    initial_tab = "details"
    initial_subview = None
    valid_tabs = {"details", "care_plan", "research", "surveys", "tools", "vitals"}

    if patient_id:
        # Verify patient exists and clinician has access
        hospital_ids = clinician.hospitals.values_list("id", flat=True)
        if Patient.objects.filter(id=patient_id, hospital_id__in=hospital_ids).exists():
            initial_patient_id = patient_id
            if tab and tab in valid_tabs:
                initial_tab = tab
            if subview:
                initial_subview = subview

    # ... existing handoff/appointment/etc code ...

    return render(request, "clinicians/dashboard.html", {
        # ... existing context ...
        "initial_patient_id": initial_patient_id,
        "initial_tab": initial_tab,
        "initial_subview": initial_subview,
    })
```

### 3. `templates/base_clinician.html`

**Add Surveys tab button** between Research and Tools (line ~114):
```html
<button role="tab"
        class="px-3 py-2.5 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'surveys' ? 'border-teal-500 text-teal-600' : 'border-transparent'"
        :style="activeTab !== 'surveys' ? 'color: var(--color-text-secondary)' : ''"
        @click="switchTab('surveys')"
        :aria-selected="activeTab === 'surveys'">
    Surveys
</button>
```

**Add data attributes** to the Alpine.js root div for initial state:
```html
<div x-data="clinicianDashboard()"
     ...
     data-initial-patient="{{ initial_patient_id|default:'' }}"
     data-initial-tab="{{ initial_tab }}"
     data-initial-subview="{{ initial_subview|default:'' }}"
     ...>
```

### 4. `static/js/clinician-dashboard.js` — Core routing logic

**New state:**
```javascript
_restoringFromUrl: false,  // Guard against re-pushing during popstate
```

**New methods:**

`_buildPath(patientId, tab, subview)` — Builds URL path from state:
```javascript
_buildPath(patientId, tab, subview) {
    if (!patientId) return '/clinician/dashboard/';
    let path = `/clinician/dashboard/patient/${patientId}/${tab || 'details'}/`;
    if (subview) path += `${subview}/`;
    return path;
}
```

`_updateUrl(opts)` — Pushes new path via `history.pushState()`:
```javascript
_updateUrl(opts = {}) {
    const path = this._buildPath(
        this.selectedPatientId,
        this.activeTab,
        opts.subview
    );
    history.pushState({ patientId: this.selectedPatientId, tab: this.activeTab, subview: opts.subview || null }, '', path);
}
```

`_restoreFromUrl()` — Parses `window.location.pathname`:
```javascript
_restoreFromUrl() {
    const match = window.location.pathname.match(
        /^\/clinician\/dashboard\/patient\/(\d+)(?:\/(\w+))?(?:\/(.+?))?\/?\s*$/
    );
    if (!match) return false;

    const [, patientId, tab, subview] = match;
    const validTabs = ['details', 'care_plan', 'research', 'surveys', 'tools', 'vitals'];
    const resolvedTab = (tab && validTabs.includes(tab)) ? tab : 'details';

    this._restoringFromUrl = true;
    this.selectedPatientId = patientId;
    this.activeTab = resolvedTab;
    this._loadTab(patientId, resolvedTab);
    this._loadChat(patientId);

    if (subview && resolvedTab === 'surveys') {
        const url = `/patient/surveys/clinician/instance/${subview}/results/`;
        setTimeout(() => {
            htmx.ajax('GET', url, {
                target: document.getElementById('detail-panel'),
                swap: 'innerHTML'
            });
        }, 100);
    }

    this._highlightPatientInList(patientId);
    this._restoringFromUrl = false;
    return true;
}
```

`_highlightPatientInList(patientId)` — Scrolls selected patient into view:
```javascript
_highlightPatientInList(patientId) {
    const tryHighlight = () => {
        const item = document.querySelector(`[data-patient-id="${patientId}"]`);
        if (item) { item.scrollIntoView({ block: 'nearest' }); return true; }
        return false;
    };
    if (!tryHighlight()) {
        document.addEventListener('htmx:afterSettle', function handler() {
            tryHighlight();
            document.removeEventListener('htmx:afterSettle', handler);
        });
    }
}
```

`navigateToSurveyResult(instanceId)` — Public method for template `@click`:
```javascript
navigateToSurveyResult(instanceId) {
    this._updateUrl({ subview: instanceId });
}
```

`backToSurveys()` — Navigate back from survey results:
```javascript
backToSurveys() {
    if (!this.selectedPatientId) return;
    this.activeTab = 'surveys';
    this._loadTab(this.selectedPatientId, 'surveys');
    this._updateUrl();
}
```

**Modified methods:**

`init()` — Add at end:
```javascript
// Restore state from URL path (deep link / bookmark / refresh)
const el = this.$el;
const initialPatient = el.dataset.initialPatient;
const initialTab = el.dataset.initialTab || 'details';
const initialSubview = el.dataset.initialSubview;

if (initialPatient) {
    this.$nextTick(() => {
        this._restoringFromUrl = true;
        this.selectedPatientId = initialPatient;
        this.activeTab = initialTab;
        this._loadTab(initialPatient, initialTab);
        this._loadChat(initialPatient);
        if (initialSubview && initialTab === 'surveys') {
            const url = `/patient/surveys/clinician/instance/${initialSubview}/results/`;
            setTimeout(() => {
                htmx.ajax('GET', url, {
                    target: document.getElementById('detail-panel'),
                    swap: 'innerHTML'
                });
            }, 100);
        }
        this._highlightPatientInList(initialPatient);
        this._restoringFromUrl = false;
    });
}

// Handle browser back/forward
window.addEventListener('popstate', () => {
    if (!this._restoreFromUrl()) {
        this.selectedPatientId = null;
        this.activeTab = 'details';
    }
});
```

`selectPatient(patientId)` — Add after existing code:
```javascript
if (!this._restoringFromUrl) this._updateUrl();
```

`switchTab(tab)` — Add after existing code:
```javascript
if (!this._restoringFromUrl) this._updateUrl();
```

Escape handler — Add `this._updateUrl()` after `this.selectedPatientId = null`.

### 5. `templates/clinicians/components/_keyboard_help.html`

Update "Switch tabs" row to show `1` through `6` kbd elements.

### 6. `templates/clinicians/components/_patient_list_item.html`

Add `data-patient-id="{{ p.id }}"` to the `<button>` element (line 3).

### 7. `templates/surveys/_tab_surveys.html`

On the "View" link (line 68), add:
```html
@click="navigateToSurveyResult('{{ instance.id }}')"
```

### 8. `templates/surveys/_survey_results.html`

Add at top of content (after opening `<div>`):
```html
<button @click="backToSurveys()"
        class="flex items-center gap-1 text-xs font-medium mb-3"
        style="color: var(--color-primary);">
    <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i>
    Back to Surveys
</button>
```

## NOT in scope

- **Patient interface navigation** — Already uses full page loads with explicit back buttons
- **Admin interface navigation** — Already uses full page loads with query parameters
- **Hash routing for schedule view** — Separate full-page view, not broken today
- **Persisting URL across login** — URL in address bar survives redirect in most browsers
- **Multi-tab coordination** — Each tab has independent state, no conflicts
- **Patient merge/archive handling** — Server validates access; stale bookmarks show empty dashboard (validated by server)

## What already exists

| Pattern | Location | Reuse |
|---------|----------|-------|
| HTMX fragment endpoints for all tabs | `apps/clinicians/urls.py`, `apps/surveys/urls.py` | Used as-is |
| `switchTab()` and `selectPatient()` | `clinician-dashboard.js:46-71` | Extended with URL calls |
| Tab URL mapping in `_loadTab()` | `clinician-dashboard.js:73-91` | Used as-is |
| `popstate` handler pattern | `base_patient.html:19` | Similar pattern |
| `data-hospital-id` attribute | `base_clinician.html:54` | Same pattern for data attrs |
| `clinician_required` decorator | `apps/clinicians/auth.py` | Already on `dashboard_view` |
| Playwright E2E conftest | `tests/e2e/conftest.py` | Extend with clinician fixtures |
| Django view test base | `apps/clinicians/tests/test_views.py:24` | Extend `ViewTestBase` |

## Failure Modes

| Failure | Test? | Error handling? | User sees? |
|---------|-------|-----------------|------------|
| Nonexistent patient in URL | Django test | Server validates → empty dashboard | Empty dashboard |
| Unauthorized patient | Django test | Server validates access → empty dashboard | Empty dashboard |
| Invalid tab name in URL | Django test | Server falls back to "details" | Details tab |
| Malformed URL path | N/A | Django returns 404 (URL doesn't match) | 404 page |
| Rapid back/forward | Playwright E2E | Each popstate triggers restore | Correct state |
| JS error in URL parsing | Fallback | try/catch in _restoreFromUrl | Empty dashboard |

No critical gaps — server validates all URL params, client handles edge cases gracefully.

## Verification

1. Start dev server, navigate to `/clinician/dashboard/`
2. Select a patient — URL updates to `/clinician/dashboard/patient/{id}/details/`
3. Switch tabs — URL updates, each tab creates new history entry
4. Click Back — returns to previous tab, then previous patient, then empty state
5. Navigate directly to `/clinician/dashboard/patient/42/surveys/` — page loads with correct patient and tab
6. Click Surveys tab → View on a result — URL updates with instance ID
7. Click "Back to Surveys" — returns to surveys tab
8. Press Escape — URL returns to `/clinician/dashboard/`
9. Refresh page — state restores from server-provided data attributes
10. Navigate to `/clinician/dashboard/patient/99999/` — shows empty dashboard (server validates)
11. Run `python manage.py test` — no regressions
12. Run Playwright E2E — all routing tests pass

## Review Decisions Made

1. **History behavior:** Every tab switch creates a new history entry (pushState), not just patient changes. User preference — Back cycles through all tabs visited.
2. **Back boundary:** Back from the first dashboard view deselects the patient (shows empty state). Another Back leaves the dashboard entirely.
3. **ID type:** Patient IDs kept as strings in JavaScript, matching existing codebase patterns.
4. **Test strategy:** Django template tests + Playwright E2E for browser behavior. No JS unit test framework setup needed.
5. **Commit strategy:** Two commits — tab button fix first (standalone), then routing (can be reverted independently).
6. **URL style:** Path-based (`/patient/42/details/`) instead of hash-based (`#patient/42/details`) for cleaner URLs and server-side validation.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 3 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

- **OUTSIDE VOICE:** Claude subagent — 10 findings, all addressed (path-based URLs address the main concern about hash fragility)
- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED — ready to implement
