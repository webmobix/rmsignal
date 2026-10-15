# Visual Design System — Julius Bär / FT-style Editorial Infographics

## 1. Overall aesthetic

**Style:** premium financial editorial + understated luxury  
**Mood:** calm, authoritative, sophisticated, data-led  
**Visual language:** minimal, spacious, restrained, highly legible

Key characteristics:

- Warm off-white background rather than pure white
- Deep navy as the dominant brand/data color
- Cool blue-grey secondary tones
- Thin-line diagrams and restrained chart styling
- Generous negative space
- Large, lightweight uppercase headings
- Almost no decorative elements
- Data visualizations are simplified and editorial
- Branding is present but visually subordinate to the content

---

## 2. Suggested color palette

### Core palette

| Role | Approx. color | Hex |
|---|---|---:|
| Warm canvas / page background | Ivory | `#F3F2E8` |
| Primary navy | Deep ink navy | `#141B4B` |
| Heading blue | Muted royal navy | `#303A78` |
| Secondary blue-grey | Dusty periwinkle | `#969CB2` |
| Light chart blue | Pale blue-grey | `#CED1DC` |
| Very light chart fill | Mist grey-blue | `#E4E6EA` |
| Neutral map / secondary fill | Warm stone | `#E4E1D3` |
| Data accent, the one non-blue | Muted antique gold | `#9A7B35` |
| Body text | Charcoal grey | `#414141` |
| Fine print | Near-black | `#262626` |

### Suggested CSS variables

```css
:root {
  --bg: #F3F2E8;
  --navy-900: #141B4B;
  --navy-700: #303A78;
  --blue-grey-500: #969CB2;
  --blue-grey-300: #CED1DC;
  --blue-grey-200: #E4E6EA;
  --stone-200: #E4E1D3;
  --gold-600: #9A7B35;   /* one chart only: the sleeve that navy cannot separate */
  --text: #414141;
  --text-dark: #262626;
}