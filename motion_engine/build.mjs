import {bundle} from '@remotion/bundler';
import {build} from 'esbuild';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
await mkdir('../static/motion', {recursive: true});
await build({entryPoints: ['src/editor.jsx'], bundle: true, outfile: '../static/motion/editor.js',
  loader: {'.woff2':'file', '.woff':'file'}, assetNames: 'fonts/[name]-[hash]', minify: true,
  define: {'process.env.NODE_ENV':'"production"'}, jsx: 'automatic'});
await bundle({entryPoint: path.resolve('src/index.jsx'), outDir: path.resolve('build'), webpackOverride: c => c});
console.log('Motion editor and renderer built');
