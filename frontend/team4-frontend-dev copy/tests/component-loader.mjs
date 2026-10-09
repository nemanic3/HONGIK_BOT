import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '..');

// Exercise the actual TSX without installing a DOM/test dependency. Only platform
// seams (Next navigation/CSS) and hook lifecycle are supplied by the test.
export function component(file, overrides = {}) {
  const cache = new Map();
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} }; cache.set(filename, module);
    const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true, target: ts.ScriptTarget.ES2022 },
      fileName: filename,
    }).outputText;
    function localRequire(name) {
      if (Object.hasOwn(overrides, name)) return overrides[name];
      if (name.endsWith('.module.css')) return { __esModule: true, default: new Proxy({}, { get: (_, key) => String(key) }) };
      if (name === 'next/image') return { __esModule: true, default: props => React.createElement('img', props) };
      if (!name.startsWith('.')) return require(name);
      const base = path.resolve(path.dirname(filename), name);
      const target = [base, `${base}.ts`, `${base}.tsx`, `${base}.jsx`].find(candidate => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
      if (!target) throw new Error(`Missing test import: ${name}`);
      return load(target);
    }
    new Function('require', 'module', 'exports', output)(localRequire, module, module.exports);
    return module.exports;
  }
  return load(path.join(root, file)).default;
}

export function hookHarness(values = []) {
  let slot = 0;
  const effects = []; const updates = [];
  const hooks = {
    ...React,
    useState(initial) {
      const index = slot++;
      return [index < values.length ? values[index] : initial, next => updates.push({ index, next })];
    },
    useEffect: callback => effects.push(callback),
    useRef: current => ({ current }),
    useCallback: callback => callback,
    useMemo: callback => callback(),
  };
  return { hooks, effects, updates };
}
export const render = (Component, props = {}) => renderToStaticMarkup(React.createElement(Component, props));
