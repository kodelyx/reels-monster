import React from 'react';
import {Composition} from 'remotion';
import {Documentary} from './Documentary';
import {DocumentaryProps} from './types';

// Everything (dimensions, fps, duration) is props-driven: the Python side
// (agent/remotion_render.py) writes remotion/props/<slug>.json and renders with
// --props. Landscape 1920x1080 by default, vertical 1080x1920 supported.
import demoProps from '../props/caption.json';

const defaultProps: DocumentaryProps = demoProps as DocumentaryProps;

export const RemotionRoot: React.FC = () => {
  return (
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
  );
};
