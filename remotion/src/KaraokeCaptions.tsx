import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Mukta';
import {CaptionPage} from './types';

const {fontFamily} = loadFont();

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// Karaoke captions — shows 2-3 words at a time with active word highlighted in gold
export const KaraokeCaptions: React.FC<{
  pages: CaptionPage[];
  gold: string;
  color: string;
}> = ({pages, gold}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const ms = (frame / fps) * 1000;

  // Find the active page
  const activePage = pages.find(p => ms >= p.startMs && ms <= p.endMs + 100);
  if (!activePage) return null;

  const allTokens = activePage.tokens;
  if (!allTokens || allTokens.length === 0) return null;

  // Keyword captions: show only the words tagged show:true (viral-reel style —
  // punchy keywords, not the whole sentence). Absent flag ⇒ shown (back-compat:
  // old caption.json with no `show` renders the full sentence exactly as before).
  const tokens = allTokens.filter((t) => t.show !== false);
  if (tokens.length === 0) return null;

  // Group consecutive keywords by time proximity. A large gap between two
  // keywords (a pause, or a run of hidden filler words) starts a new group, and
  // no group holds more than MAX_WORDS. This ties each on-screen line to what is
  // actually being spoken instead of stapling far-apart keywords together.
  const GROUP_GAP_MS = 700;
  const MAX_WORDS = 3;
  const groups: typeof tokens[] = [];
  for (let i = 0; i < tokens.length; i++) {
    const prev = i > 0 ? tokens[i - 1] : null;
    const gap = prev ? tokens[i].startMs - prev.endMs : 0;
    const last = groups[groups.length - 1];
    if (!prev || gap > GROUP_GAP_MS || last.length >= MAX_WORDS) {
      groups.push([tokens[i]]);
    } else {
      last.push(tokens[i]);
    }
  }

  // Active group: visible from its first word's start until the NEXT group's
  // first word starts, so it holds through the gap instead of flickering off.
  let activeGroup = groups[0];
  for (let g = 0; g < groups.length; g++) {
    const groupStart = groups[g][0].startMs;
    const nextStart = g + 1 < groups.length ? groups[g + 1][0].startMs : Infinity;
    if (ms >= groupStart && ms < nextStart) {
      activeGroup = groups[g];
      break;
    }
  }

  // Progressive reveal: within the active group show only words already spoken
  // (a small lead so a word lands just as it's said). Nothing appears early.
  const LEAD_MS = 120;
  const visible = activeGroup.filter((t) => ms >= t.startMs - LEAD_MS);
  if (visible.length === 0) return null;

  const vertical = height > width;
  const fontSize = vertical ? 54 : 60;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: vertical ? 440 : 96,
        left: 0,
        width: '100%',
        textAlign: 'center',
        fontFamily,
        fontWeight: 800,
        fontSize,
        lineHeight: 1.15,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          display: 'inline-block',
          background: 'rgba(0,0,0,0.65)',
          padding: '12px 32px',
          borderRadius: 24,
          textShadow: '0 3px 0 rgba(0,0,0,0.8), 0 0 20px rgba(0,0,0,0.4)',
        }}
      >
        {visible.map((token) => {
          const isActive = ms >= token.startMs && ms <= token.endMs + 50;
          return (
            <span
              key={token.startMs}
              style={{
                color: isActive ? gold : '#FFFFFF',
                margin: '0 10px',
                display: 'inline-block',
                transform: isActive ? 'scale(1.08)' : 'scale(1.0)',
                transition: 'transform 0.08s ease, color 0.08s ease',
              }}
            >
              {token.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};
