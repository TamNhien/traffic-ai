import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const css = fs.readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')
const jsx = fs.readFileSync(new URL('../src/main.jsx', import.meta.url), 'utf8')
const security = fs.readFileSync(new URL('../src/security.jsx', import.meta.url), 'utf8')
const theme = css.split('/* V0.5.125: coherent native dark-mode controls', 2)[1] || ''

test('form theme is dark by default including native dropdowns', () => {
  assert.match(theme, /color-scheme:\s*dark/)
  assert.match(theme, /:where\(\.app-shell, \.auth-page\)/)
  assert.match(theme, /select\s*:\s*is\(option, optgroup\)/)
  assert.match(theme, /--traffic-field-bg:\s*#[0-9a-f]{6}/i)
  assert.match(theme, /--traffic-field-text:\s*#[0-9a-f]{6}/i)
})

test('dataset, fine-tune and sign-in all use the shared form theme', () => {
  for(const cls of ['dataset-form', 'train-form', 'dataset-select', 'auth-page']) {
    assert.ok(cls === 'auth-page' ? security.includes(cls) || jsx.includes(cls) : jsx.includes(cls), `${cls} not found`)
  }
  for(const selector of ['input:not([type="checkbox"])', 'select,', 'textarea', '::placeholder', ':focus-visible']) {
    assert.ok(theme.includes(selector), `${selector} not themed`)
  }
})

test('checkboxes, radio, file and button controls are not rendered as text fields', () => {
  for(const kind of ['checkbox','radio','range','file','hidden','button','submit','reset','color']) {
    assert.ok(theme.includes(`:not([type="${kind}"])`), `${kind} should be exempt`)
  }
  assert.match(theme, /accent-color:/)
})

test('Chrome and Edge autofill preserve dark password and username fields', () => {
  assert.match(theme, /input:-webkit-autofill/)
  assert.match(theme, /-webkit-text-fill-color:\s*var\(--traffic-field-text\)/)
  assert.match(theme, /-webkit-box-shadow:\s*0 0 0 1000px var\(--traffic-field-bg\) inset/)
  assert.match(css, /\.password-input-wrap input/)
  assert.match(css, /\.auth-box input/)
})

test('dark form change is CSS only and the existing training workflow stays intact', () => {
  assert.match(jsx, /setDatasetForm/)
  assert.match(jsx, /setTrainingForm/)
  assert.match(jsx, /onChange=\{e=>setDatasetForm/)
  assert.match(jsx, /onChange=\{e=>setTrainingForm/)
})
