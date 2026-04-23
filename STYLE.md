# TubeSum — Style Reference

## Colours

| Variable | Hex | Used for |
|---|---|---|
| `--bg-dark` | `#0f0f0f` | Page background |
| `--bg-card` | `#1a1a1a` | Cards, panels |
| `--bg-input` | `#2a2a2a` | Input fields, config sections |
| `--text` | `#ffffff` | Primary text |
| `--text-muted` | `#a0a0a0` | Secondary text, labels |
| `--border` | `#333333` | Borders, dividers |
| `--primary` | `#8b5cf6` | Purple — focus rings, active states |
| `--success` | `#10b981` | Green — success states |
| `--error` | `#ef4444` | Red — errors, delete |
| `--warning` | `#f59e0b` | Amber — warnings |
| `--info` | `#3b82f6` | Blue — info, doc links |

### Accent colour — Pink
TubeSum's brand accent is **pink** (`#ec4899`).
All primary buttons (Summarize, Go Pro, Create account) use a purple-to-pink gradient:

```css
background: linear-gradient(135deg, #8b5cf6, #ec4899);
```

The dominant perceived colour is pink — this is TubeSum's identity colour within the Dehesa Studio family.

---

## Font

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```

System font stack — no external fonts loaded. Uses OS default sans-serif.

---

## Dehesa Studio app accent colours

Each app shares the same dark foundation but has its own accent:

| App | Accent | Hex |
|---|---|---|
| TubeSum | Pink | `#ec4899` |
| Reforesta | Terracotta | `#C4601A` |
| Dehesa Studio (landing) | Olive green | `#a8bc6e` |

---

*Last updated: April 2026*
