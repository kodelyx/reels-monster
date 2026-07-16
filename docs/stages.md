# 📋 Reels-Monster Stage-by-Stage Guide

Reels-Monster pipeline me total **12 stages (00 se 11)** hain. Har stage ka ek set inputs (`requires`) aur ek set outputs (`produces`) hota hai. Ek stage ka output agle stage ka input banta hai.

---

## ── Phase 1: Text Generation (LLM Core) ──

### 🎬 Stage 00: Topic Generator (`00_topic`)
* **Summary:** Reel ka topic decide karta hai.
* **Requires:** `profile/profile.json` (Aapka channel profile data, niche, tone instructions).
* **Produces:** `project/topic.json` (decided topic, visual context, main angle).
* **Kaise kaam karta hai:** Channel preferences ke hisab se AI se trend-matching, click-worthy topics generate karwata hai.

---

### 🔍 Stage 01: Preproduction (`01_preproduction`)
* **Summary:** Topic ke upar factual research aur script direction ready karta hai.
* **Requires:** `project/topic.json`
* **Produces:** `project/scripting/pre_production.json` (deep facts, hook strategy, visual theme).
* **Kaise kaam karta hai:** AI research agent topic ko analyze karta hai aur use target audience ke liye "fact-heavy, engaging angle" me convert karta hai.

---

### ✍️ Stage 02: Script Writer (`02_script`)
* **Summary:** Audio narration ke liye final Hindi script likhta hai.
* **Requires:** `project/scripting/pre_production.json`
* **Produces:** `project/scripting/script.json` (5 distinct scenes with narration).
* **Kaise kaam karta hai:** Script Devnagari script (Hindi characters) me likhi jati hai. Har segment ka timing, pace, aur emotion set kiya jata hai.

---

### 🎨 Stage 03: Scene Designer (`03_scenes`)
* **Summary:** Har scene ke visual B-roll videos ki prompts design karta hai.
* **Requires:** `project/scripting/script.json`
* **Produces:** `project/scripting/scenes.json` (scene-wise camera instructions & video prompts).
* **Kaise kaam karta hai:** Script ke har segment ke according visually matching dynamic video prompts design karta hai jo bad me video generator model me use honge.

---

### 🎵 Stage 04: Music Prompt (`04_music_prompt`)
* **Summary:** Background music ke liye customized prompt taiyar karta hai.
* **Requires:** `project/scripting/script.json`
* **Produces:** `project/scripting/music_prompt.txt`
* **Kaise kaam karta hai:** Pure reel ke tone aur content ke according aisi description likhta hai jisse sound generators dynamic track compose kar sakein.

---

## ── Phase 2: Media Production & Rendering ──

### 🗣️ Stage 05: Avatar Generation (`05_avatar`)
* **Summary:** Narrator AI talking head avatar generate karta hai.
* **Requires:** `project/scripting/script.json`, `profile/avatar.jpg`
* **Produces:** `project/avatar/scene_N.mp4` (scene-wise raw speaking videos).
* **Kaise kaam karta hai:** Flow Video API me narrator avatar image aur audio voice synthesis model call karke face animates, matching speech generate kiye jaate hain.

---

### ✂️ Stage 06: Audio Process & Align (`06_process`)
* **Summary:** Silence trimming, audio level normalization aur word-level timings extract karta hai.
* **Requires:** `project/avatar/scene_N.mp4`, `project/scripting/script.json`
* **Produces:** `project/avatar/scene_N.mp4` (trimmed/clean), `project/scripting/caption.json` (global timing timeline).
* **Kaise kaam karta hai (Enhancements):**
  1. AI voice audio analyze karke start/end timings extract karta hai.
  2. `rapid_edit.py` silence trim karke clip clean banata hai.
  3. **Loudness Normalization (New):** -14.0 LUFS standard loudness check lagta hai jisse koi scene dhima aur koi tez na ho.
  4. **Phonetic Merges (New):** "ए" + "आई" jaise split words ko automatic merge karke display captions me custom English "AI" ya "ChatGPT" term replace karta hai.

---

### 🖼️ Stage 07: Popup Designer (`07_popups`)
* **Summary:** Screen pe float karne wale motion graphic cards design aur sync karta hai.
* **Requires:** `project/scripting/caption.json`
* **Produces:** `project/scripting/caption.json` (modified with popup structure & sync timings).
* **Kaise kaam karta hai (Enhancements):**
  1. **Dynamic SFX scan:** `sfx/` folder ko auto-scan karta hai aur unki list AI ko bhejta hai.
  2. **AI sound selection:** AI narration and keywords dekh kar context ke according best sound effect (Alert, Success chime, Riser, swoosh) filter out karke write-down karta hai.
  3. Remotion render configuration file (`PopupAsset.tsx`) ke andr automatic naye audio tracks populate aur sync kar deta hai.

---

### 📼 Stage 08: B-Roll Generator (`08_broll`)
* **Summary:** Background visual reels generate karta hai.
* **Requires:** `project/scripting/scenes.json`
* **Produces:** `project/broll/scene_N_a.mp4`, `project/broll/scene_N_b.mp4` (2 videos per scene).
* **Kaise kaam karta hai:** Flow Text-to-Video engine se parallelly scenes prompts se raw loops download karke workspace directory structure complete ki jati hai.

---

### 🎹 Stage 09: Music Production (`09_music`)
* **Summary:** Gemini se dynamic audio soundtrack download karta hai.
* **Requires:** `project/scripting/music_prompt.txt`
* **Produces:** `project/music/bg_music.mp3` (also symlinks into Remotion assets).
* **Kaise kaam karta hai:** Local wrapper/mcp-server call hota hai jo Gemini models use karke background soundtrack build karta hai.

---

### 🧪 Stage 10: Video Composer (`10_render`)
* **Summary:** Video template, images, text, B-rolls aur sound components ko blend karke final output file rendering.
* **Requires:** `caption.json`, and all assets in `avatar/`, `broll/`, `music/`, `sfx/`
* **Produces:** `output/final.mp4`
* **Kaise kaam karta hai:** Remotion React structures call karke dynamic audio balance dynamic transitions (zoom, overlap) render out karke single unified video compile kar deta hai.

---

### 🏁 Stage 11: Final Trim (`11_final_trim`)
* **Summary:** Pure complete video pe final trim edits apply karta hai.
* **Requires:** `output/final.mp4`
* **Produces:** `output/final_trimmed.mp4`
* **Kaise kaam karta hai:** Agreable time offsets (keep frames config file) check karke composite timeline cuts short kar deta hai, jisse dynamic frame adjustments perfect finish ho sakein.
