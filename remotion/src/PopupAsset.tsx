import { AbsoluteFill, Audio, Sequence, interpolate, spring, staticFile, useCurrentFrame } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Montserrat';
import { loadFont as loadCaptionFont } from '@remotion/google-fonts/Mukta';
import * as SI from 'simple-icons';
import type { PopupConfig } from './types';

const { fontFamily: POPUP_FONT } = loadFont();
// Same font the karaoke captions use, so popup text matches the caption look.
const { fontFamily: CAPTION_FONT } = loadCaptionFont();

// ─────────────────────────────────────────────
// SOUND SYSTEM
// ─────────────────────────────────────────────
// SFX library — curated for each moment type
const SFX = {
  // Card pop-in (main element appears)
  pop:       'sfx/transition-sfx-1-62531.mp3',    // clean short transition pop
  popSoft:   'sfx/bubble-pop.mp3',                 // soft bubble pop for sub-items
  popHard:   'sfx/pop_1.mp3',                      // harder pop for final reveal
  // Swoosh / whoosh (motion cards)
  swoosh:    'sfx/swoosh-simple-66449.mp3',        // smooth fast swoosh
  swooshHard:'sfx/fast-whoosh.mp3',                // fast sharp whoosh
  // Shine / glow (success / highlight)
  shine:     'sfx/shine-brightness-sound-effect-85192.mp3', // premium shine
  shineAnime:'sfx/anime-shine-sound-effect_QP4mAaX.mp3',    // anime-style shine
  // Impact (dramatic moment)
  impact:    'sfx/sudden-impact-1.mp3',            // dramatic impact
  boom:      'sfx/cinematic-boom.mp3',             // cinematic boom
  // Rise (build-up, reveal)
  rise:      'sfx/popular-riser.mp3',              // riser for stat reveals
  // Notification / tick (each sub-node)
  ding:      'sfx/ding-sound-effect_1.mp3',        // soft ding
  success:   'sfx/success-chime.mp3',              // success chime
  // CTA / Warning
  alert:     'sfx/metal-gear-solid-alert_LjQWbMe.mp3', // clean sharp alert beep

  // ── auto-added by stage 07 ──
  'anime-shine-sound-effect_QP4mAaX': 'sfx/anime-shine-sound-effect_QP4mAaX.mp3',  // shine / sparkle / glow
  'bubble-pop': 'sfx/bubble-pop.mp3',  // pop / bubble
  'cinematic-boom': 'sfx/cinematic-boom.mp3',  // dramatic impact / explosion
  'ding-sound-effect_1': 'sfx/ding-sound-effect_1.mp3',  // notification / ding
  'fast-whoosh': 'sfx/fast-whoosh.mp3',  // motion swoosh / whoosh
  'metal-gear-solid-alert_LjQWbMe': 'sfx/metal-gear-solid-alert_LjQWbMe.mp3',  // alert / warning
  pop_1: 'sfx/pop_1.mp3',  // pop / bubble
  'popular-riser': 'sfx/popular-riser.mp3',  // pop / bubble
  'shine-brightness-sound-effect-85192': 'sfx/shine-brightness-sound-effect-85192.mp3',  // shine / sparkle / glow
  'success-chime': 'sfx/success-chime.mp3',  // notification / ding
  'sudden-impact-1': 'sfx/sudden-impact-1.mp3',  // hard impact / hit
  'swoosh-simple-66449': 'sfx/swoosh-simple-66449.mp3',  // motion swoosh / whoosh
  'transition-sfx-1-62531': 'sfx/transition-sfx-1-62531.mp3',  // transition / slide
};

// SfxAudio helper: runs inside Sequence context so localFrame is reset to 0
const SfxAudio: React.FC<{ src: string; volume: number; len: number }> = ({ src, volume, len }) => {
  const localFrame = useCurrentFrame();
  const fadeOut = localFrame >= len - 12
    ? interpolate(localFrame, [len - 12, len], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;
  return <Audio src={staticFile(src)} volume={volume * fadeOut} />;
};

// Sfx component: plays audio starting at trigger frame for a limited duration.
// Wraps in <Sequence> so the audio playhead starts correctly from the beginning (frame 0).
// Volume is scaled by 0.25 globally to make sound effects extremely quiet and subtle.
type SfxProps = { at: number; src: string; volume?: number; lf: number; len?: number };
const Sfx: React.FC<SfxProps> = ({ at, src, volume = 0.7, len = 45 }) => {
  const scaledVolume = volume * 0.25;
  return (
    <Sequence from={at} durationInFrames={len}>
      <SfxAudio src={src} volume={scaledVolume} len={len} />
    </Sequence>
  );
};


const ICONS = {
  chatgpt: (c: string) => <svg viewBox="0 0 24 24" width="85" height="85"><path fill={c} d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>,
  robot: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M20 9V7c0-1.1-.9-2-2-2h-3c0-1.66-1.34-3-3-3S9 3.34 9 5H6c-1.1 0-2 .9-2 2v2c-1.66 0-3 1.34-3 3s1.34 3 3 3v4c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4c1.66 0 3-1.34 3-3s-1.34-3-3-3zm-11 4c-.83 0-1.5-.67-1.5-1.5S8.17 10 9 10s1.5.67 1.5 1.5S9.83 13 9 13zm6 0c-.83 0-1.5-.67-1.5-1.5S14.17 10 15 10s1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1 4H8v-2h8v2z"/></svg>,
  check: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>,
  code: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/></svg>,
  brain: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M12 2a9 9 0 00-9 9c0 3.88 2.46 7.19 5.9 8.45.08-.54.22-1.06.42-1.55A7 7 0 015 11a7 7 0 0114 0 7 7 0 01-3.32 5.9c.2.49.34 1.01.42 1.55A9 9 0 0021 11a9 9 0 00-9-9zm0 4a5 5 0 00-5 5c0 1.86 1.02 3.49 2.53 4.35.3-.46.66-.87 1.08-1.22A3 3 0 019 11a3 3 0 016 0 3 3 0 01-1.61 2.66 5.97 5.97 0 011.08 1.69A5 5 0 0017 11a5 5 0 00-5-5z"/></svg>,
  human: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>,
  gear: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>,
  shield: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>,
  question: (c: string) => <svg viewBox="0 0 24 24" width="90" height="90"><path fill={c} d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.9C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.04-.42 1.99-1.07 2.75z"/></svg>,
  google: () => (
    <svg viewBox="0 0 24 24" width="80" height="80">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
    </svg>
  ),
  microsoft: () => (
    <svg viewBox="0 0 23 23" width="70" height="70">
      <rect x="0" y="0" width="10.5" height="10.5" fill="#F25022"/>
      <rect x="11.5" y="0" width="10.5" height="10.5" fill="#7FBA00"/>
      <rect x="0" y="11.5" width="10.5" height="10.5" fill="#00A4EF"/>
      <rect x="11.5" y="11.5" width="10.5" height="10.5" fill="#FFB900"/>
    </svg>
  ),
  amazon: () => (
    <svg viewBox="0 0 24 24" width="75" height="75">
      <path fill="#FF9900" d="M19.93 15.65c-1.38 1.25-3.8 2.03-5.59 2.03-2.6 0-4.94-.86-6.62-2.28-.2-.17-.03-.43.21-.3.73.38 2.27.91 3.51.91 1.7 0 3.82-.44 5.37-1.52.26-.18.52.12.12.38s-.8 1.01-1.07 1.07c-2.31 1.34-6.4 1.12-8.73-.59-.19-.14-.07-.37.16-.27 2.22.95 6.07.6 8.52-.77.12-.07.28.1.13.22z"/>
      <path fill="#FF9900" d="M20.25 14.18c-.14-.38-.55-.38-.79-.17l-1.62 1.43c-.15.13-.1.35.08.38l2.25.32c.24.03.41-.18.3-.39l-.22-.39z"/>
    </svg>
  ),
};

const CARD = 250;                 // card side (px) — larger for mobile readability
const RADIUS = 42;                // corner radius

// Base glass card. A premium multi-layer look: deep tinted glass with a soft
// vertical gradient, heavy blur, and a hairline highlight. Border + inner
// highlights + sheen are layered on top as separate elements per card.
const G: React.CSSProperties = {
  background: 'linear-gradient(160deg, rgba(22,26,40,0.82) 0%, rgba(9,11,20,0.88) 100%)',
  backdropFilter: 'blur(30px) saturate(1.3)', WebkitBackdropFilter: 'blur(30px) saturate(1.3)',
  borderRadius: `${RADIUS}px`,
  display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', position: 'absolute',
  overflow: 'hidden',
};

function ep(lf: number, dur: number, len = 14): number {
  const s = dur - len;
  return lf >= s ? interpolate(lf - s, [0, len], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 1;
}

// hex + alpha byte (0..1) → "#rrggbbaa"
function hexA(hex: string, a: number): string {
  const h = (hex || '#60A5FA').replace('#', '').slice(0, 6).padEnd(6, '0');
  const aa = Math.round(Math.max(0, Math.min(1, a)) * 255).toString(16).padStart(2, '0');
  return `#${h}${aa}`;
}

// ─────────────────────────────────────────────
// DATA-DRIVEN POPUP SYSTEM
// Popups are generated per scene by scripts/popup_designer.py and passed in via
// scene.popup. Icons resolve to: emoji text | simple-icons brand logo | curated SVG.
// ─────────────────────────────────────────────

type SimpleIconData = { path: string; hex: string; title: string; slug: string };

// simple-icons v16 exports `si<Slug>` (e.g. "openai" -> siOpenai, "1password" -> si1password)
const siBySlug = (slug: string): SimpleIconData | null => {
  const s = (slug || '').trim();
  if (!s) return null;
  const varName = 'si' + s.charAt(0).toUpperCase() + s.slice(1);
  const found = (SI as Record<string, unknown>)[varName] as SimpleIconData | undefined;
  return found && found.path ? found : null;
};

const IconView: React.FC<{ icon: PopupConfig['cards'][number]['icon']; color: string; size?: number }> = ({ icon, color, size = 84 }) => {
  if (!icon) return <div style={{ fontSize: size * 0.8, lineHeight: 1 }}>✨</div>;
  if (icon.type === 'emoji') {
    return <div style={{ fontSize: size * 0.82, lineHeight: 1 }}>{icon.value}</div>;
  }
  if (icon.type === 'svg') {
    const fn = (ICONS as Record<string, ((c?: string) => JSX.Element) | undefined>)[icon.value];
    return fn ? fn(color) : <div style={{ fontSize: size * 0.8, lineHeight: 1 }}>✨</div>;
  }
  // simpleicon — keep the brand's own color (contract: real logos stay on-brand)
  const si = siBySlug(icon.value);
  if (!si || !si.path || !si.hex) return <div style={{ fontSize: size * 0.8, lineHeight: 1 }}>✨</div>;
  return (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <path fill={`#${si.hex}`} d={si.path} />
    </svg>
  );
};

// Horizontal slot grid (±250px card spacing). CARD/2 = half card width to center.
const SLOT_X: Record<string, string> = {
  left:   `calc(50% - 285px - ${CARD / 2}px)`,
  center: `calc(50% - ${CARD / 2}px)`,
  right:  `calc(50% + 285px - ${CARD / 2}px)`,
};

// Renders one scene's popup config: staggered glass cards synced to spoken words + SFX.
const PopupScene: React.FC<{ config: PopupConfig; fps: number; dur: number }> = ({ config, fps, dur }) => {
  const lf = useCurrentFrame();            // already scene-local (PopupAsset is inside the scene Sequence)
  const x = ep(lf, dur);
  const msToF = (ms: number) => Math.round((ms / 1000) * fps);

  const cards = config.cards ?? [];
  const slotSeen: Record<string, number> = {};

  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      {(config.sfx ?? []).map((s, i) => {
        const src = SFX[s.key as keyof typeof SFX];
        return src ? <Sfx key={`sfx${i}`} lf={lf} at={msToF(s.atMs)} src={src} volume={s.volume ?? 0.7} /> : null;
      })}

      {cards.map((c, i) => {
        const delay = msToF(c.atMs);
        const sp = spring({ frame: Math.max(0, lf - delay), fps, config: { damping: 12, mass: 0.9 } });
        const since = lf - delay;                        // frames since this card entered
        const breathe = 1 + Math.sin(lf * 0.07 + i * 1.3) * 0.012;   // subtle idle breathing so holds never look frozen
        const scale = interpolate(sp, [0, 1], [0.62, 1]) * x * breathe;
        const opacity = sp > 0 ? x : 0;
        const rise = interpolate(sp, [0, 1], [26, 0]);   // slide up into place
        const enterBlur = interpolate(since, [0, 10], [10, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const floatY = Math.sin(lf * 0.09 + i * 2) * 6;

        // Vertical nudge if a slot repeats, so cards never overlap
        const slot = c.slot in SLOT_X ? c.slot : (['left', 'center', 'right'][i % 3] as 'left' | 'center' | 'right');
        const seen = slotSeen[slot] ?? 0;
        slotSeen[slot] = seen + 1;
        const topOffset = seen === 0 ? 0 : (seen % 2 === 1 ? 116 : -116) * Math.ceil(seen / 2);

        return (
          <div key={`card${i}`} style={{
            position: 'absolute',
            left: SLOT_X[slot], top: `calc(50% - ${CARD / 2}px + ${topOffset}px)`,
            width: CARD, height: CARD,
            display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
            transform: `scale(${scale}) translateY(${floatY + rise}px)`,
            opacity,
            filter: enterBlur > 0.2 ? `blur(${enterBlur}px)` : undefined,
          }}>
            {/* icon with a soft colored glow — no card, floats free over the video */}
            <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <div style={{
                position: 'absolute', width: 132, height: 132, borderRadius: '50%',
                background: `radial-gradient(circle, ${hexA(c.color, c.accent ? 0.55 : 0.40)} 0%, ${hexA(c.color, 0)} 70%)`,
                filter: 'blur(3px)', pointerEvents: 'none',
                opacity: 0.7 + Math.sin(lf * 0.11 + i) * 0.15,
              }} />
              <div style={{ filter: `drop-shadow(0 3px 12px ${hexA(c.color, 0.7)})`, display: 'flex' }}>
                <IconView icon={c.icon} color={c.color} size={92} />
              </div>
            </div>

            {/* label — styled exactly like the karaoke captions: Mukta, bold, white
                with a heavy dark outline/shadow so it reads over any video, no box */}
            <div style={{
              fontFamily: CAPTION_FONT, fontSize: 40, fontWeight: 800, marginTop: 16, color: '#FFFFFF',
              letterSpacing: 0.5, textAlign: 'center', padding: '0 4px', lineHeight: 1.12,
              textTransform: 'uppercase',
              textShadow: '0 3px 0 rgba(0,0,0,0.85), 0 0 14px rgba(0,0,0,0.75), 0 2px 6px rgba(0,0,0,0.9)',
              WebkitTextStroke: '1px rgba(0,0,0,0.55)',
            }}>{c.label}</div>
            {c.sub && <div style={{
              fontFamily: CAPTION_FONT, fontSize: 30, fontWeight: 700, color: '#FFFFFF', marginTop: 8, letterSpacing: 0.3,
              textAlign: 'center', lineHeight: 1.12, textTransform: 'uppercase',
              textShadow: '0 2px 0 rgba(0,0,0,0.85), 0 0 12px rgba(0,0,0,0.7), 0 1px 4px rgba(0,0,0,0.9)',
              WebkitTextStroke: '0.75px rgba(0,0,0,0.5)',
            }}>{c.sub}</div>}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Public API: renders a scene's data-driven popup overlay. Rendered inside the
// scene <Sequence>, so useCurrentFrame() is scene-local; each card self-delays via atMs.
export const PopupAsset: React.FC<{ popup?: PopupConfig; duration: number; fps?: number }> = ({ popup, duration, fps = 30 }) => {
  if (!popup || !popup.cards || popup.cards.length === 0) return null;
  return <PopupScene config={popup} fps={fps} dur={duration} />;
};
