import React from 'react';
import { staticFile } from 'remotion';
import { loadFont } from '@remotion/google-fonts/ArchivoBlack';

// Archivo Black — a wide, heavy, blocky grotesque, the closest match to the
// bold impact headline used on reference reels ("BILLIONAIRES / NEVER LOSE").
const { fontFamily } = loadFont();

type Word = { text: string; color: string };

// The headline is split across (usually) two lines the same way the reference
// does it: the render stage marks where the break goes with a word whose text
// is exactly "\n". Absent ⇒ everything stays on one line.
function splitLines(words: Word[]): Word[][] {
  const lines: Word[][] = [[]];
  for (const w of words) {
    if (w.text === '\n') {
      lines.push([]);
    } else {
      lines[lines.length - 1].push(w);
    }
  }
  return lines.filter((l) => l.length > 0);
}

/**
 * Reference-reel top headline: heavy condensed uppercase words, each word its
 * own colour, with a grunge texture eroded INTO the letters (multiply blend of
 * a speckled mask clipped to the text) so it reads as spray-stencil, not a flat
 * web font. Data-driven from style.title.
 */
export const TitleBar: React.FC<{ words: Word[] }> = ({ words }) => {
  if (!words || words.length === 0) return null;
  const lines = splitLines(words);

  return (
    <div
      style={{
        position: 'absolute',
        // Pushed DOWN out of Instagram's top UI band (profile / audio strip
        // eat the first ~12% of the frame and would clip the headline).
        top: 150,
        left: 0,
        width: '100%',
        textAlign: 'center',
        padding: '0 36px',
        fontFamily,
        fontWeight: 400, // Archivo Black is single-weight and already ultra-bold
        fontSize: 84,
        lineHeight: 1.0,
        letterSpacing: 0,
        textTransform: 'uppercase',
        pointerEvents: 'none',
      }}
    >
      {lines.map((line, li) => (
        <div key={li} style={{ position: 'relative', display: 'block' }}>
          {line.map((w, i) => (
            <span
              key={i}
              style={{
                position: 'relative',
                display: 'inline-block',
                margin: '0 6px',
                color: w.color,
                // hard drop shadow + glow so it pops off the dark bg like the ref
                textShadow:
                  '0 5px 0 rgba(0,0,0,0.85), 0 0 26px rgba(0,0,0,0.7), 4px 4px 0 rgba(0,0,0,0.4)',
                // grunge: the texture image is used as a mask so a FINE, subtle
                // grain eats into the coloured glyphs (distressed print look) —
                // the letters stay mostly solid, only lightly eroded.
                WebkitMaskImage: `url(${staticFile('grunge.png')})`,
                maskImage: `url(${staticFile('grunge.png')})`,
                WebkitMaskSize: '340px 115px',
                maskSize: '340px 115px',
                WebkitMaskRepeat: 'repeat',
                maskRepeat: 'repeat',
              }}
            >
              {w.text}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
};
