# 🎬 Reels-Monster: Pipeline Stages Quick Guide

Reels-Monster pipeline me total **12 stages (00 to 11)** hain. Har stage pichle stage ke output par depend karta hai.

---

### 📊 Quick Overview Table

| Stage | Name | Inputs (`Requires`) | Outputs (`Produces`) | Core Action (Simple Hindi) |
| :--- | :--- | :--- | :--- | :--- |
| **00** | **Topic** | `profile/profile.json` | `project/topic.json` | Niche ke according trending topic decide karna |
| **01** | **Preproduction** | `project/topic.json` | `scripting/pre_production.json` | Topic par facts aur research collect karna |
| **02** | **Script** | `scripting/pre_production.json` | `scripting/script.json` | Narration script likhna (Hindi Devanagari) |
| **03** | **Scenes** | `scripting/script.json` | `scripting/scenes.json` | B-Roll clips ke liye text prompts likhna |
| **04** | **Music Prompt** | `scripting/script.json` | `scripting/music_prompt.txt` | Sound generation ke liye style-theme guide banana |
| **05** | **Avatar** | `scripting/script.json` | `project/avatar/scene_N.mp4` | Synthesized voice aur talking avatar video banana |
| **06** | **Process** | `project/avatar/scene_N.mp4` | Trimmed video + `scripting/caption.json` | Silence trimming, timing alignment + audio normalizer |
| **07** | **Popups** | `scripting/caption.json` | Updated `caption.json` with popups | Glass-card popups aur matching SFX lagana |
| **08** | **B-roll** | `scripting/scenes.json` | `project/broll/scene_N_a/b.mp4` | Flow API se visuals generate aur download karna |
| **09** | **Music** | `scripting/music_prompt.txt` | `project/music/bg_music.mp3` | Gemini se custom background music compose karana |
| **10** | **Render** | All generated assets | `output/final.mp4` | Remotion engine se screen render compile karna |
| **11** | **Final Trim** | `output/final.mp4` | `output/final_trimmed.mp4` | Video borders aur frames ke according final tight trim |

---

## 🛠️ Detailed Stage Mechanics

### Phase 1: Text & Scripting (LLM)

#### 00_topic
- **Kaam:** Aapke profile guidelines ko follow karke ek hot click-worthy topic select karta hai.

#### 01_preproduction
- **Kaam:** Us topic ke details verify karta hai, interesting facts nikalta hai aur reel ki storyboard approach decide karta hai.

#### 02_script
- **Kaam:** final voiceover narration likhta hai (strictly Hindi Devanagari script).

#### 03_scenes
- **Kaam:** Video visuals ko describe karta hai. Har segment me background visual kaisa dikhna chahiye, uski detail commands design karta hai.

#### 04_music_prompt
- **Kaam:** Background soundtrack ke parameters (mood, BPM, instrument style) define karta hai.

---

### Phase 2: Media & Generation (APIs & Rendering)

#### 05_avatar
- **Kaam:** Flow API ko trigger karke aapki profile photo (`avatar.jpg`) aur script audio ko ek single speaking video clip me convert karta hai.

#### 06_process
- **Kaam:** 
  - **Trimming:** Faltu silent portions ko cut karta hai.
  - **Loudness Norm:** Audio voice ko standardized `-14 LUFS` level par shift karta hai taaki volume uniform rahe.
  - **Phonetic Merges:** Captions me "ए आई" ko auto-replace karke English readable display keyword "AI" banata hai.

#### 07_popups
- **Kaam:** 
  - Voice timing ke sync me graphic glass cards set karta hai.
  - `sfx/` folder ko automatically scan karke keyword ke according appropriate sound (Ding, alert, success chime) select karta hai.

#### 08_broll
- **Kaam:** Stage 03 ke visual prompts ko Flow video generator me upload karke 4-seconds ke background loop videos download karta hai.

#### 09_music
- **Kaam:** Gemini Lyria/music system se background music generate karta hai aur host directory paths me connect karta hai.

#### 10_render
- **Kaam:** Remotion/Bun engine ke setup links connect karke video blocks, overlays, aur audio clips ko merge karke final raw production file compile karta hai.

#### 11_final_trim
- **Kaam:** Custom timestamp targets follow karke dynamic cut windows apply karta hai taaki end results perfect speed me sync rahein.
