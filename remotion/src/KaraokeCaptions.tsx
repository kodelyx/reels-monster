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

  // Chunk tokens into groups of 3 words
  const chunkSize = 3;
  const chunks: typeof tokens[] = [];
  for (let i = 0; i < tokens.length; i += chunkSize) {
    chunks.push(tokens.slice(i, i + chunkSize));
  }

  // Find the active chunk. Each chunk stays visible from its first word's start
  // until the NEXT chunk's first word starts — so during the filler-word gaps
  // (hidden words) the last keyword group holds instead of flickering off.
  let activeChunk = chunks[0];
  for (let c = 0; c < chunks.length; c++) {
    const chunkStart = chunks[c][0].startMs;
    const nextStart = c + 1 < chunks.length ? chunks[c + 1][0].startMs : Infinity;
    if (ms >= chunkStart && ms < nextStart) {
      activeChunk = chunks[c];
      break;
    }
  }

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
        {activeChunk.map((token, index) => {
          const isActive = ms >= token.startMs && ms <= token.endMs + 50;
          return (
            <span
              key={index}
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
