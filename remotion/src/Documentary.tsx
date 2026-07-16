import React from 'react';
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { DocumentaryProps } from './types';
import { KaraokeCaptions } from './KaraokeCaptions';
import { PopupAsset } from './PopupAsset';

// ---------------------------------------------------------------------------
// Scene transition wrappers
// ---------------------------------------------------------------------------
// ... (rest of transitions) ...

// Frames over which the LAST scene fades to black, so the video closes smoothly
// instead of hard-cutting on the final frame.
const CLOSE_FADE = 16;


/**
 * Crossfade (Dissolve): outgoing scene fades out, incoming scene fades in
 * during the overlap window. First scene skips fade-in (hook must be instant).
 */
const CrossfadeWrap: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  overlap: number;
  isFirst: boolean;
  isLast: boolean;
}> = ({ children, durationInFrames, overlap, isFirst, isLast }) => {
  const frame = useCurrentFrame();

  // Fade in at the start (except first scene — hook must be instant)
  const fadeIn = isFirst
    ? 1
    : interpolate(frame, [0, overlap], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  // Fade out at the end. Last scene fades to black over CLOSE_FADE frames (smooth
  // close); middle scenes fade over the overlap window (crossfade into the next).
  const fadeOut = isLast
    ? interpolate(
      frame,
      [durationInFrames - CLOSE_FADE, durationInFrames],
      [1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    : interpolate(
      frame,
      [durationInFrames - overlap, durationInFrames],
      [1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    );

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>{children}</AbsoluteFill>
  );
};

/**
 * Zoom Dissolve: crossfade + slight zoom-in on exit, zoom-out on entry.
 * Popular for explainer/reels content.
 */
const ZoomDissolveWrap: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  overlap: number;
  isFirst: boolean;
  isLast: boolean;
}> = ({ children, durationInFrames, overlap, isFirst, isLast }) => {
  const frame = useCurrentFrame();

  // Fade in + zoom out (1.08 → 1.0) at the start
  const fadeIn = isFirst
    ? 1
    : interpolate(frame, [0, overlap], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  const scaleIn = isFirst
    ? 1
    : interpolate(frame, [0, overlap], [1.08, 1.0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  // Fade out + zoom in (1.0 → 1.08) at the end. Last scene fades to black over
  // CLOSE_FADE frames (with a gentle zoom) so the video closes smoothly.
  const fadeOut = isLast
    ? interpolate(
      frame,
      [durationInFrames - CLOSE_FADE, durationInFrames],
      [1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    : interpolate(
      frame,
      [durationInFrames - overlap, durationInFrames],
      [1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    );
  const scaleOut = isLast
    ? interpolate(
      frame,
      [durationInFrames - CLOSE_FADE, durationInFrames],
      [1.0, 1.05],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    : interpolate(
      frame,
      [durationInFrames - overlap, durationInFrames],
      [1.0, 1.08],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    );

  const scale = scaleIn * scaleOut;

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <AbsoluteFill
        style={{ transform: `scale(${scale})`, transformOrigin: 'center center' }}
      >
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
/**
 * Slide (Page Transition): slide outgoing scene to the left, slide incoming
 * scene from the right with a spring timing feel.
 */
const SlideWrap: React.FC<{
  children: React.ReactNode;
  durationInFrames: number;
  overlap: number;
  isFirst: boolean;
  isLast: boolean;
}> = ({ children, durationInFrames, overlap, isFirst, isLast }) => {
  const frame = useCurrentFrame();

  // Slide in from the right at the start (1080px -> 0px)
  const slideInX = isFirst
    ? 0
    : interpolate(frame, [0, overlap], [1080, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  // Slide out to the left at the end (0px -> -1080px)
  const slideOutX = isLast
    ? 0
    : interpolate(
      frame,
      [durationInFrames - overlap, durationInFrames],
      [0, -1080],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    );

  const translateX = slideInX + slideOutX;

  return (
    <AbsoluteFill style={{ transform: `translateX(${translateX}px)` }}>
      {children}
    </AbsoluteFill>
  );
};


/**
 * Simple 8-frame fade-in — used when no transition overlap is set ('none').
 */
const SimpleFade: React.FC<{ children: React.ReactNode; skip?: boolean }> = ({ children, skip }) => {
  const frame = useCurrentFrame();
  const opacity = skip ? 1 : interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

// ─── Audio Ducking Configuration ───
// BG Music volume levels for 3-layer ducking:
//   VOICE_DUCK  = when narration is playing (most of the time)
//   SFX_DUCK    = when SFX triggers in PopupAsset (extra low so SFX pops)
//   TRANSITION  = during scene crossfade gaps (music swells slightly)
const DUCK = { voice: 0.08, sfx: 0.04, transition: 0.22 } as const;

export const Documentary: React.FC<DocumentaryProps> = ({ fps, scenes, pages, style }) => {
  // SFX trigger frames per scene, DERIVED from each scene's popup.sfx (the same
  // data PopupAsset plays), so BG-music ducking always matches the real SFX.
  const SFX_WINDOWS: Record<number, number[]> = {};
  scenes.forEach((scene, i) => {
    SFX_WINDOWS[i] = (scene.popup?.sfx ?? []).map(s => Math.round((s.atMs / 1000) * (fps || 30)));
  });
  const transition = style.transition ?? 'crossfade';
  const overlap = style.overlapFrames ?? 0;
  const globalFrame = useCurrentFrame();

  // ─── Pre-compute scene timing for ducking ───
  let computeFrom = 0;
  const sceneTiming: { from: number; to: number; index: number }[] = [];
  scenes.forEach((scene, i) => {
    const sceneFrom = i === 0 ? 0 : computeFrom - overlap;
    sceneTiming.push({ from: sceneFrom, to: sceneFrom + scene.durationInFrames, index: i });
    computeFrom = sceneFrom + scene.durationInFrames;
  });

  // ─── Dynamic BG Music volume with ducking ───
  const bgMusicVolume = (frame: number): number => {
    // Find which scene this frame belongs to
    const currentScene = sceneTiming.find(s => frame >= s.from && frame < s.to);
    if (!currentScene) return DUCK.transition; // between scenes or before/after

    const localFrame = frame - currentScene.from;
    const sceneIdx = currentScene.index;

    // Check if we're in an SFX window (starts 2 frames early, lasts 45 frames)
    const sfxTriggers = SFX_WINDOWS[sceneIdx] || [];
    const inSfxWindow = sfxTriggers.some(t => localFrame >= t - 2 && localFrame <= t + 45);

    if (inSfxWindow) {
      // Extra duck during SFX so sound effects cut through clearly
      return DUCK.sfx;
    }

    // Check if we're in a transition overlap zone
    const isInOverlapStart = localFrame < overlap && currentScene.index > 0;
    const isInOverlapEnd = localFrame > (currentScene.to - currentScene.from - overlap) && currentScene.index < scenes.length - 1;
    if (isInOverlapStart || isInOverlapEnd) {
      // Slight music swell during transitions
      return DUCK.transition;
    }

    // Normal: duck under narration
    return DUCK.voice;
  };

  let from = 0;
  const sequences = scenes.map((scene, i) => {
    const isFirst = i === 0;
    const isLast = i === scenes.length - 1;

    // Each scene after the first starts `overlap` frames earlier so the
    // outgoing and incoming scenes play on top of each other during the
    // transition window.
    const sceneFrom = isFirst ? 0 : from - overlap;

    // Data-driven popup overlay (generated by scripts/popup_designer.py). Each
    // card self-delays via its atMs, so it only needs the scene duration.
    const popupElement: React.ReactNode = scene.popup?.cards?.length
      ? <PopupAsset popup={scene.popup} duration={scene.durationInFrames} fps={fps || 30} />
      : null;

    // Top panel B-roll. If a 2nd clip exists, play the two back-to-back within
    // the scene (each ~half the scene) so they read as one continuous shot.
    const brollStyle = { width: '100%', height: '100%', objectFit: 'cover' } as const;
    const brollNode: React.ReactNode = scene.brollSrc2
      ? (
        <>
          <Sequence from={0} durationInFrames={Math.ceil(scene.durationInFrames / 2)}>
            <OffthreadVideo src={staticFile(scene.brollSrc)} style={brollStyle} muted playbackRate={scene.playbackRate ?? 1} />
          </Sequence>
          <Sequence from={Math.ceil(scene.durationInFrames / 2)}>
            <OffthreadVideo src={staticFile(scene.brollSrc2)} style={brollStyle} muted playbackRate={scene.playbackRate ?? 1} />
          </Sequence>
        </>
      )
      : <OffthreadVideo src={staticFile(scene.brollSrc)} style={brollStyle} muted playbackRate={scene.playbackRate ?? 1} />;

    // Wrap the B-roll element with transitions if overlap is active
    let wrappedBroll: React.ReactNode = (
      <>
        {brollNode}
        {popupElement}
      </>
    );

    if (transition === 'zoom-dissolve' && overlap > 0) {
      wrappedBroll = (
        <ZoomDissolveWrap
          durationInFrames={scene.durationInFrames}
          overlap={overlap}
          isFirst={isFirst}
          isLast={isLast}
        >
          {wrappedBroll}
        </ZoomDissolveWrap>
      );
    } else if (transition === 'crossfade' && overlap > 0) {
      wrappedBroll = (
        <CrossfadeWrap
          durationInFrames={scene.durationInFrames}
          overlap={overlap}
          isFirst={isFirst}
          isLast={isLast}
        >
          {wrappedBroll}
        </CrossfadeWrap>
      );
    } else if (transition === 'slide' && overlap > 0) {
      wrappedBroll = (
        <SlideWrap
          durationInFrames={scene.durationInFrames}
          overlap={overlap}
          isFirst={isFirst}
          isLast={isLast}
        >
          {wrappedBroll}
        </SlideWrap>
      );
    } else {
      wrappedBroll = (
        <SimpleFade skip={isFirst}>{wrappedBroll}</SimpleFade>
      );
    }

    const videoElement = (
      <AbsoluteFill style={{ backgroundColor: 'black', display: 'flex', flexDirection: 'column', padding: 40, gap: 30, justifyContent: 'center' }}>
        {/* Top Half: B-roll */}
        <div style={{
          width: '100%',
          height: '45%',
          position: 'relative',
          overflow: 'hidden',
          borderRadius: 32,
          border: '4px solid white',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.4)',
        }}>
          {wrappedBroll}
        </div>

        {/* Bottom Half: Avatar */}
        <div style={{
          width: '100%',
          height: '45%',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: '#000',
          borderRadius: 32,
          border: '4px solid white',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.4)',
        }}>
          {scene.avatarSrc ? (
            <OffthreadVideo
              src={staticFile(scene.avatarSrc)}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              volume={1.4}
              playbackRate={1.0}
            />
          ) : (
            <div style={{ color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>No Avatar</div>
          )}
        </div>
      </AbsoluteFill>
    );

    const seq = (
      <Sequence key={scene.index} from={sceneFrom} durationInFrames={scene.durationInFrames}>
        {videoElement}
      </Sequence>
    );
    from = sceneFrom + scene.durationInFrames;
    return seq;
  });

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      {/* BG Music with dynamic ducking — ducks under narration & SFX */}
      <Sequence from={0}>
        <Audio src={staticFile('bg_music.mp3')} volume={bgMusicVolume} loop />
      </Sequence>
      {sequences}
      {/* Captions MUST stay at the root, after all Sequences */}
      <KaraokeCaptions pages={pages} gold={style.gold} color={style.captionColor} />
    </AbsoluteFill>
  );
};
