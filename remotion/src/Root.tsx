import React from 'react';
import {Composition} from 'remotion';
import {Documentary} from './Documentary';
import {DocumentaryProps} from './types';
import {EndCard, endCardSchema} from './EndCard';

// Everything (dimensions, fps, duration) is props-driven: the Python side
// (agent/remotion_render.py) writes remotion/props/<slug>.json and renders with
// --props. Landscape 1920x1080 by default, vertical 1080x1920 supported.
// Studio default props. Uses caption.json (regenerated early by stage 06), NOT
// caption.render.json — the render copy is only created at stage 10, so importing
// it would break the studio/typecheck on a fresh project (after cleanup) until a
// render has run. The title still appears in the RENDER itself, which passes
// --props=caption.render.json explicitly (independent of this default).
import demoProps from '../props/caption.json';

const defaultProps: DocumentaryProps = demoProps as DocumentaryProps;

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="Documentary"
      component={Documentary}
      durationInFrames={300}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
      calculateMetadata={({props}) => {
        const overlap = props.style.overlapFrames ?? 0;
        const total = props.scenes.reduce((sum, s) => sum + s.durationInFrames, 0);
        // Correct composition duration: total frames minus overlap frames for each transition
        const actualDuration = total - (props.scenes.length - 1) * overlap;
        return {
          durationInFrames: Math.max(actualDuration, 30),
          fps: props.fps,
          width: props.width,
          height: props.height,
          props,
        };
      }}
    />
    {/* Animated outro end-card (Instagram Follow CTA). Rendered separately by
        stage 10 and concatenated onto the tail of the video. Portrait 1080x1920,
        150 frames (5s) @ 30fps. */}
    <Composition
      id="EndCard"
      component={EndCard}
      durationInFrames={150}
      fps={30}
      width={1080}
      height={1920}
      schema={endCardSchema}
      defaultProps={{
        ctaText: 'Follow',
        subText: 'for more like this',
        handle: '@Kodeylx',
        gradFrom: '#feda75',
        gradMid: '#d62976',
        gradTo: '#4f5bd5',
        bgTop: '#1a0a24',
        bgBottom: '#070310',
      }}
    />
    </>
  );
};
