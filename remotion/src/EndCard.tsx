import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  Easing,
  useCurrentFrame,
  useVideoConfig,
  random,
} from "remotion";
import { z } from "zod";

// ---- Dynamic props (edit live in the Studio right sidebar) ----
export const endCardSchema = z.object({
  ctaText: z.string(),
  subText: z.string(),
  handle: z.string(),
  gradFrom: z.string(),
  gradMid: z.string(),
  gradTo: z.string(),
  bgTop: z.string(),
  bgBottom: z.string(),
});

export type EndCardProps = z.infer<typeof endCardSchema>;

const OUT = Easing.bezier(0.16, 1, 0.3, 1);

const useSpring = (delay: number, cfg?: { damping?: number; stiffness?: number; mass?: number }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({
    frame: frame - delay,
    fps,
    config: { damping: 12, stiffness: 130, mass: 0.8, ...cfg },
  });
};

const rgba = (hex: string, a: number) => {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
};

const bloom = (color: string, base: number, intensity = 1) =>
  [1, 2, 4, 8]
    .map((m, i) => `0 0 ${base * m}px ${rgba(color, (0.5 / (i + 1)) * intensity)}`)
    .join(", ");

// ---------- animated film grain ----------
const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  const seed = Math.floor(frame / 2) % 6;
  return (
    <AbsoluteFill style={{ opacity: 0.5, mixBlendMode: "soft-light", pointerEvents: "none" }}>
      <svg width="100%" height="100%">
        <filter id={`n${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#n${seed})`} opacity="0.5" />
      </svg>
    </AbsoluteFill>
  );
};

// ---------- floating gradient blobs (depth) ----------
const Blobs: React.FC<{ a: string; b: string; c: string }> = ({ a, b, c }) => {
  const frame = useCurrentFrame();
  const blob = (x: number, y: number, size: number, color: string, sp: number) => ({
    position: "absolute" as const,
    left: `${x + Math.sin(frame / sp) * 4}%`,
    top: `${y + Math.cos(frame / (sp * 1.2)) * 4}%`,
    width: size,
    height: size,
    borderRadius: "50%",
    background: `radial-gradient(circle, ${rgba(color, 0.22)}, transparent 65%)`,
    filter: "blur(70px)",
  });
  return (
    <AbsoluteFill>
      <div style={blob(6, 10, 480, a, 42)} />
      <div style={blob(64, 66, 540, c, 55)} />
      <div style={blob(70, 6, 360, b, 48)} />
      <div style={blob(4, 70, 400, b, 60)} />
    </AbsoluteFill>
  );
};

// ---------- heart burst on entrance ----------
const HeartBurst: React.FC<{ colors: string[] }> = ({ colors }) => {
  const frame = useCurrentFrame();
  const start = 14;
  if (frame < start) return null;
  const t = frame - start;
  const pieces = new Array(14).fill(0).map((_, i) => {
    const ang = (i / 14) * Math.PI * 2 + random(`a${i}`) * 0.5;
    const dist = interpolate(t, [0, 30], [0, 300 + random(`d${i}`) * 160], {
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
    const op = interpolate(t, [0, 20, 38], [1, 1, 0], { extrapolateRight: "clamp" });
    const size = 20 + random(`s${i}`) * 18;
    return {
      x: Math.cos(ang) * dist,
      y: Math.sin(ang) * dist - t * 2,
      op,
      size,
      color: colors[i % colors.length],
    };
  });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      {pieces.map((p, i) => (
        <svg
          key={i}
          viewBox="0 0 24 24"
          width={p.size}
          height={p.size}
          style={{
            position: "absolute",
            opacity: p.op,
            transform: `translate(${p.x}px, ${p.y}px)`,
            filter: `drop-shadow(0 0 6px ${p.color})`,
          }}
        >
          <path d="M12 21s-7-4.5-9.5-8.5C.5 9 2 5.5 5.2 5.5c1.9 0 3.1 1.1 3.8 2.2C9.7 6.6 10.9 5.5 12.8 5.5 16 5.5 17.5 9 15.5 12.5 13 16.5 12 21 12 21z" fill={p.color} />
        </svg>
      ))}
    </AbsoluteFill>
  );
};

// ---------- Instagram-style camera glyph in gradient ring ----------
const IgIcon: React.FC<{ from: string; mid: string; to: string; scale: number; squash: number }> = ({
  from,
  mid,
  to,
  scale,
  squash,
}) => {
  const frame = useCurrentFrame();
  const glow = interpolate(Math.sin(frame / 12), [-1, 1], [0.7, 1]);
  return (
    <div
      style={{
        width: 250,
        height: 250,
        borderRadius: 66,
        transform: `scale(${scale * (1 + squash)}, ${scale * (1 - squash)})`,
        background: `linear-gradient(135deg, ${from} 0%, ${mid} 50%, ${to} 100%)`,
        boxShadow: `${bloom(mid, 14, glow)}, inset 0 6px 18px ${rgba("#ffffff", 0.4)}, inset 0 -12px 26px ${rgba("#000000", 0.35)}, 0 22px 44px ${rgba("#000000", 0.5)}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg width="140" height="140" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" style={{ filter: "drop-shadow(0 3px 5px rgba(0,0,0,0.35))" }}>
        <rect x="3" y="3" width="18" height="18" rx="5.5" />
        <circle cx="12" cy="12" r="4.2" />
        <circle cx="17.2" cy="6.8" r="1.3" fill="#fff" stroke="none" />
      </svg>
    </div>
  );
};

export const EndCard: React.FC<EndCardProps> = ({
  ctaText,
  subText,
  handle,
  gradFrom,
  gradMid,
  gradTo,
  bgTop,
  bgBottom,
}) => {
  const frame = useCurrentFrame();
  const LEAD = 4; // trim dead time at start — pull entrance forward
  const f = frame + LEAD;

  const bgFade = interpolate(f, [0, 6], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.quad) });

  // smooth, gentle entrances
  const iconPop = useSpring(2 - LEAD, { damping: 16, stiffness: 90, mass: 1 });
  const squash = f < 2 ? 0 : Math.max(0, Math.sin(interpolate(f, [2, 22], [0, Math.PI], { extrapolateRight: "clamp" })) * 0.1) * (f < 22 ? 1 : 0);

  const handleIn = interpolate(f, [12, 30], [0, 1], { extrapolateRight: "clamp", easing: OUT });
  const subIn = interpolate(f, [18, 36], [0, 1], { extrapolateRight: "clamp", easing: OUT });
  const btnSpring = useSpring(26 - LEAD, { damping: 15, stiffness: 95, mass: 1 });
  const btnScale = interpolate(btnSpring, [0, 1], [0.82, 1]);
  const btnPress = 0;
  const socialIn = useSpring(44 - LEAD, { damping: 14, stiffness: 100 });

  const floaty = Math.sin(frame / 32) * 6;
  const btnGlow = interpolate(Math.sin(frame / 14), [-1, 1], [0.7, 1]);

  return (
    <AbsoluteFill style={{ opacity: bgFade, overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `linear-gradient(165deg, ${bgTop} 0%, ${bgBottom} 100%)` }} />
      <Blobs a={gradFrom} b={gradMid} c={gradTo} />
      {/* darken blobs so bg stays rich, not milky */}
      <AbsoluteFill style={{ background: rgba("#000000", 0.28) }} />
      <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 45%, transparent 42%, rgba(0,0,0,0.62) 100%)" }} />

      <HeartBurst colors={[gradFrom, gradMid, gradTo]} />

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 46, transform: `translateY(${floaty}px)`, padding: "0 40px" }}>
          {/* IG icon */}
          <div style={{ opacity: interpolate(f, [2, 12], [0, 1], { extrapolateRight: "clamp", easing: OUT }) }}>
            <IgIcon from={gradFrom} mid={gradMid} to={gradTo} scale={interpolate(iconPop, [0, 1], [0.72, 1])} squash={squash} />
          </div>

          {/* handle */}
          <div
            style={{
              opacity: handleIn,
              transform: `translateY(${interpolate(handleIn, [0, 1], [24, 0])}px)`,
              color: "#fff",
              fontFamily: "'Arial', Helvetica, sans-serif",
              fontWeight: 800,
              fontSize: 58,
              letterSpacing: 0.5,
              textShadow: "0 3px 14px rgba(0,0,0,0.5)",
            }}
          >
            {handle}
          </div>

          {/* subtext */}
          <div
            style={{
              opacity: subIn,
              transform: `translateY(${interpolate(subIn, [0, 1], [20, 0])}px)`,
              color: rgba("#ffffff", 0.7),
              fontFamily: "'Arial', sans-serif",
              fontWeight: 500,
              fontSize: 34,
              marginTop: -22,
            }}
          >
            {subText}
          </div>

          {/* Follow button (IG gradient) */}
          <div
            style={{
              opacity: btnSpring,
              transform: `scale(${btnScale * (1 - btnPress)})`,
              padding: "34px 110px",
              borderRadius: 22,
              background: `linear-gradient(120deg, ${gradFrom} 0%, ${gradMid} 55%, ${gradTo} 100%)`,
              color: "#fff",
              fontFamily: "'Arial', Helvetica, sans-serif",
              fontWeight: 800,
              fontSize: 66,
              letterSpacing: 0.5,
              boxShadow: `${bloom(gradMid, 14, btnGlow)}, inset 0 3px 0 ${rgba("#ffffff", 0.35)}, inset 0 -6px 0 ${rgba("#000000", 0.22)}, 0 14px 0 ${rgba(gradTo, 0.4)}, 0 24px 40px ${rgba("#000000", 0.5)}`,
              textShadow: "0 2px 6px rgba(0,0,0,0.3)",
              position: "relative",
              overflow: "hidden",
              whiteSpace: "nowrap",
            }}
          >
            {ctaText}
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "46%", background: `linear-gradient(180deg, ${rgba("#ffffff", 0.25)}, transparent)`, borderRadius: "22px 22px 0 0", pointerEvents: "none" }} />
            <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
              <div
                style={{
                  position: "absolute",
                  top: -20,
                  bottom: -20,
                  width: "35%",
                  left: `${interpolate(frame % 100, [0, 100], [-50, 170])}%`,
                  background: "linear-gradient(100deg, transparent, rgba(255,255,255,0.32), transparent)",
                  transform: "skewX(-18deg)",
                }}
              />
            </div>
          </div>

          {/* IG social row: heart / comment / send / save */}
          <div style={{ opacity: socialIn, transform: `scale(${interpolate(socialIn, [0, 1], [0.85, 1])})` }}>
            <SocialIcons frame={frame} accent={gradMid} />
          </div>
        </div>
      </AbsoluteFill>

      <Grain />
    </AbsoluteFill>
  );
};

const SocialIcons: React.FC<{ frame: number; accent: string }> = ({ frame, accent }) => {
  const active = Math.floor(frame / 16) % 4;
  const pop = (i: number) => {
    if (i !== active) return 1;
    const local = (frame % 16) / 16;
    return 1 + Math.sin(local * Math.PI) * 0.32;
  };
  const stroke = { stroke: "#fff", strokeWidth: 2, fill: "none" };
  const Chip: React.FC<{ children: React.ReactNode; i: number }> = ({ children, i }) => (
    <div
      style={{
        transform: `scale(${pop(i)})`,
        width: 100,
        height: 100,
        borderRadius: "50%",
        background: "rgba(255,255,255,0.1)",
        border: "2px solid rgba(255,255,255,0.22)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: i === active ? `0 0 26px ${accent}, inset 0 0 18px ${rgba(accent, 0.4)}` : "0 6px 16px rgba(0,0,0,0.35)",
      }}
    >
      {children}
    </div>
  );
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
      {/* heart */}
      <Chip i={0}>
        <svg viewBox="0 0 24 24" width="52" height="52">
          <path {...stroke} d="M12 21s-7-4.5-9.5-8.5C.5 9 2 5.5 5.2 5.5c1.9 0 3.1 1.1 3.8 2.2C9.7 6.6 10.9 5.5 12.8 5.5 16 5.5 17.5 9 15.5 12.5 13 16.5 12 21 12 21z" strokeLinejoin="round" />
        </svg>
      </Chip>
      {/* comment */}
      <Chip i={1}>
        <svg viewBox="0 0 24 24" width="52" height="52">
          <path {...stroke} d="M21 11.5a8.4 8.4 0 01-9 8 9 9 0 01-4-1L3 20l1.5-4.5A8.4 8.4 0 013 11.5 8.5 8.5 0 0112 3a8.4 8.4 0 019 8.5z" strokeLinejoin="round" />
        </svg>
      </Chip>
      {/* send / share */}
      <Chip i={2}>
        <svg viewBox="0 0 24 24" width="52" height="52">
          <path {...stroke} d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </Chip>
      {/* save / bookmark */}
      <Chip i={3}>
        <svg viewBox="0 0 24 24" width="52" height="52">
          <path {...stroke} d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z" strokeLinejoin="round" />
        </svg>
      </Chip>
    </div>
  );
};
