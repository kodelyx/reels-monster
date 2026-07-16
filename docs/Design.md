# 🎨 Design.md — reels-monster

> Visual system — colors, theme, fonts, layout, motion. Ye **final video** ka look define karta hai (UI app nahi, ye video output hai). Source of truth: `remotion/src/*`. Rules jo yahan hain, un se AI stages (script/scenes/popups) aur Remotion dono bandhe hain.

---

## 1. Overall look & feel
**Dark, cinematic, premium documentary reel.** Low-key lighting, high contrast, moody. Instagram Reels / YouTube Shorts ke liye — thumb-stopping first 4 seconds.

- **Orientation**: Portrait **9:16** (`1080 × 1920`). *(Composition landscape 1920×1080 default rakhta hai par props se vertical set hota hai — reels ke liye vertical.)*
- **FPS**: 30 (props-driven)
- **Mood words**: dark, sleek, mysterious, "wow / is this real"

---

## 2. Screen layout (split-screen)
```
┌─────────────────────────┐  ← 1080 wide
│                         │
│        B-ROLL           │  Upar: topic-relevant motion clip
│      (top screen)       │  (Flow API se, t2v)
│                         │
│   [ glass popup cards ] │  ← icon popups B-roll ke upar float
├─────────────────────────┤
│                         │
│    TALKING AVATAR       │  Neeche: creator avatar bolta hua
│     (bottom screen)     │  (Flow API, trimmed)
│                         │
│   ▓ karaoke captions ▓  │  ← neeche, active word gold me
└─────────────────────────┘  1920 tall
```

---

## 3. Color palette
| Role | Value | Kahan |
|:--|:--|:--|
| **Accent / gold** (active caption, hero popup) | `style.gold` (props-driven) | KaraokeCaptions active word, popup accent |
| Caption text (inactive) | `#FFFFFF` | Karaoke non-active words |
| Caption background | `rgba(0,0,0,0.65)` | Caption strip behind text |
| Base theme | **Dark / low-key** | Poori video |
| Popup cards | **Glassmorphic** — translucent + blur + colored accent (`color: "#RRGGBB"` per card) | `PopupAsset.tsx` |

> Exact gold value render ke time `caption.json → style.gold` se aata hai (per-project tunable). Popup card colors AI (`07 popups`) story ke hisaab se deta hai.

---

## 4. Typography
| Element | Font | Weight | Size |
|:--|:--|:--|:--|
| **Karaoke captions** | **Mukta** (`@remotion/google-fonts/Mukta`) | 800 | 54px (vertical) / 60px (landscape) |
| Popup label/sub | glass-card style | bold label + lighter sub | `PopupAsset.tsx` |

Text effects: `textShadow: 0 3px 0 rgba(0,0,0,0.8), 0 0 20px rgba(0,0,0,0.4)` — readability over busy B-roll.

---

## 5. Motion / transitions
- Scene transitions: `style.transition` = `crossfade | zoom-dissolve | slide | none` (+ `overlapFrames`).
- Karaoke: active word gold me + halka scale, `transition: transform 0.08s, color 0.08s`.
- Popups: `atMs` pe spoken word ke saath pop-in, slot `left|center|right`, `accent` hero card ko stronger glow.

---

## 6. Content/creative hard-rules (AI stages inhe follow karein)
> Ye `Rules.md R17` ke visual boundaries hain — script/scenes/popups generate karte waqt inse deviate nahi.

- **Lighting**: hamesha **dark / low-key**.
- **Frames me text/logo/watermark nahi** (captions Remotion overlay karta hai, generated video me nahi).
- **B-roll = t2v** (text-to-video), narration TTS overlay hai — B-roll me koi bole nahi.
- **No human-actor/celebrity-face** scenes (profile `avoid_topics`).
- Visuals AI khud topic ke hisaab se decide kare — koi fixed theme nahi, par easy-to-generate + relevant.
- **Max 4 parallel** video generations (Flow credits/limits).

---

## 7. Source of truth
| Cheez | File |
|:--|:--|
| Composition size/fps/duration | `remotion/src/Root.tsx` |
| Split-screen + transitions | `remotion/src/Documentary.tsx` |
| Caption look | `remotion/src/KaraokeCaptions.tsx` |
| Popup/glass cards | `remotion/src/PopupAsset.tsx`, `PopupConfig` in `types.ts` |
| Data shape | `remotion/src/types.ts` (`DocumentaryProps`) |

> **Remotion Phase 2-5 me change NAHI hoga** (Rules R1). Design.md ise document karta hai taaki AI stages iske hisaab se content banayein.
