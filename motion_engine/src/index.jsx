import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Film, durationFrames} from './film';
import './fonts.css';
const Root = () => <Composition id="GoldGen" component={Film} width={1080} height={1920} fps={30}
  durationInFrames={30} defaultProps={{manifest: {scenes: []}}}
  calculateMetadata={({props}) => ({durationInFrames: durationFrames(props.manifest)})}/>;
registerRoot(Root);
