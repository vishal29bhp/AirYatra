# AirYatra theme

The look comes from the Vaayu Prive deck (master prompt section C.4). The product name stays AirYatra.

## Where the tokens live

| File | What it holds |
|---|---|
| `frontend/src/index.css` | shadcn CSS variables for the light theme (`:root`) and the dark theme (`.dark`, the default). Also global heading fonts and the `.ay-overline` pattern |
| `frontend/tailwind.config.js` | Font families (`font-sans`, `font-heading`, `font-mono`), 4px radius, `lime` and `amber` brand colours, and the **slate scale remapped to aubergine** |
| `frontend/public/index.html` | Google Fonts (`display=swap`), `theme-color`, colours for the first paint |
| `frontend/src/components/shared/ThemeToggle.js` | CSS variables that the light/dark toggle sets |
| `design_guidelines.json` | Rules for building new screens |

The screens use `slate-*` classes for nearly every surface, border and secondary text: about 10,000 usages. Remapping
slate in Tailwind themes all of them at once, with no per-component edits:

| slate | 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 950 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hex | `#F8F6FA` | `#F2EEF6` | `#E2DCE9` | `#D0C9DA` | `#A69DB3` | `#8B819C` | `#5A5068` | `#3A3046` | `#221A2D` | `#17111F` | `#0F0B15` |

Two shades differ from the deck, both for accessibility:
- slate-400 and the dark `muted-foreground` are `#A69DB3` instead of `#A197AE`, so that labels on `#3A3046` reach 4.5:1.
- slate-500 is `#8B819C` instead of `#716785`. About 600 usages put slate-500 on body text, and the deck's `#716785` is only 3.5:1.

## Contrast (WCAG 2.1, AA = 4.5:1 body text, 3:1 large text)

Dark theme:

| Text | on page `#17111F` | on card `#221A2D` | on raised `#3A3046` |
|---|---|---|---|
| Primary text `#F2EEF6` | 16.14 (AA) | 14.63 (AA) | 10.84 (AA) |
| Secondary text (slate-300) `#D0C9DA` | 11.48 (AA) | 10.41 (AA) | 7.72 (AA) |
| Muted text (slate-400, shadcn `muted-foreground`) `#A69DB3` | 7.12 (AA) | 6.46 (AA) | 4.79 (AA) |
| Subtle text (slate-500; not for use on raised panels) `#8B819C` | 5.03 (AA) | 4.56 (AA) | 3.38 (AA large only) |
| Lime accent as text/icon `#C8F23C` | 14.27 (AA) | 12.94 (AA) | 9.59 (AA) |
| Amber highlight `#FFB000` | 10.09 (AA) | 9.14 (AA) | 6.78 (AA) |

Light theme and fills:

| Pair | Ratio |
|---|---|
| Text `#17111F` on page `#F2EEF6` | 16.14 (AA) |
| Text `#17111F` on card `#FFFFFF` | 18.48 (AA) |
| Muted `#5A5068` on page `#F2EEF6` | 6.59 (AA) |
| Muted `#5A5068` on card `#FFFFFF` | 7.55 (AA) |
| Black on lime (primary button) | 16.22 (AA) |
| White on destructive `#DC2626` | 4.83 (AA) |

Lime is never used as text on a light background. On white it is 1.1:1.

## Still to do (screen by screen)

- The brand accent in today's screens is orange (`orange-400/500/600`, about 1,800 usages, mostly with white text).
  Lime needs black text, so a global remap would break contrast. Accents move to lime by hand, one primary action per view, in this order: Landing, Booking flow, Login, Customer dashboard, Payment, then the Operator and Admin dashboards.
- `blue-*` highlights (about 800 usages) move to lime or amber in the same pass.
- Headlines should adopt the `.ay-overline` pattern, and cards should drop rounded corners and shadows (`rounded-sm`, no `shadow-*`).
