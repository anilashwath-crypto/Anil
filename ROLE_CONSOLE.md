# Role drill-down console

`Role_Drilldown_Dashboard.html` — a single-file, no-build prototype of a **role-aware
drill-down dashboard** for the ERP permission model (19 internal roles + portal users).

The point: a user picks their role once, and the console lands them on the handful of
things that role actually does. No menu-bar hunting, no scrolling past 71 modules to
find the 6 they can touch.

Design language (tokens, sidebar, breadcrumb drill-down, KPI/card idiom) is borrowed
from the Ommi Forge ERP dashboard v2.12 for consistency; **the content is entirely the
permission configuration of this ERP**, which is a different system.

## What it does

| Surface | Purpose |
| --- | --- |
| **Role home** | Access stats, a pinned "your daily loop" tile row, your module groups, watch-outs on your role, and an explicit *"not yours — request access"* block so people stop searching for what they'll never find |
| **Group → Module drill-down** | Breadcrumb stack, `← Back`, `Alt+←`. Modules you can't reach stay visible but greyed, with the reason |
| **Module detail** | A literal checklist of what you can do here (read / create / edit / delete / approve), which flags land on this module, which other roles touch it, and where you usually go next |
| **Access matrix** | 20 roles × 71 modules, filterable by group. Click any cell to jump into that role's view of that module |
| **Permission audit** | The 11 findings from the 30-Jul-2026 review, severity-filtered, each linking straight to the affected role + module |
| **All roles** | Directory with owned / editable / view / approve counts and open flag count per role |

Also: module search (`/` to focus, arrows + Enter), light/dark theme that respects both
the OS preference and a manual override, print stylesheet, and a mobile layout that
swaps the sidebar for a horizontal nav.

Role choice and theme persist in `localStorage`, so the second visit lands straight on
the user's own home.

## Where the data lives

Everything renders from one block at the top of the `<script>`:

- `GROUPS` — 13 functional groups (Sales & CRM, Planning & PPC, Shop Floor, … Admin)
- `MODULES` — 71 modules, each tagged with its group and a one-line description
- `ROLES` — 20 entries: `perms` (the access map), `remit`, `pins` (the daily-loop tiles),
  plus optional `scopeNote` / `scopedModules` for row-level scoping (Operator, Portal)
- `FINDINGS` — the audit findings, each linked to the roles and modules it affects

Permission levels are a compact string: `0` none · `1` view · `2` view+create ·
`3` view+create+edit · `4` all (incl. delete). An `a` suffix adds an approve right
(`'1a'` = view + approve); level `4` always carries approve.

```js
DIRECTOR: allExcept('1', {              // view-only baseline …
  ENQUIRIES:'1a', QUOTATIONS:'1a',      // … plus approval rights
  CRM:'4', REPORTS:'4',                 // … plus full control
  USER_MANAGEMENT:'0',                  // … minus what's denied
})
```

## Keeping it honest

The matrix is **transcribed from the 30-Jul-2026 audit of `shared/permissions.ts`**, not
read live from the code — that file isn't in this repository. To wire it to the real
thing, generate the `ROLES[].perms` maps from `shared/permissions.ts` (a small script that
walks the exported role object and emits the level strings) and drop them into the data
block. Nothing below the data block needs to change.

`PLANNER` is a special case: the source defines it twice (lines 423 and 628) and the
second definition silently wins. The console shows the **effective** (second) set and
keeps the overwritten first set alongside it in `permsShadow`, so the conflict is visible
rather than lost.

## Open questions before this goes further

1. **Pinned tiles are hand-written per role.** They encode a guess at each role's daily
   loop. Worth reviewing with two or three actual users per role before building the real
   thing — the pins are the whole value of the page.
2. **Real counts.** Every tile is currently a label; the live version should carry the
   number that makes it worth clicking ("7 NCRs open", "12 POs awaiting approval").
3. **Operator department scoping** is shown as a note, not enforced — the model here is
   role-level, and the real system scopes MES queues to the operator's own department.
