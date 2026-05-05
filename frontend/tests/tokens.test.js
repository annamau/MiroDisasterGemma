import { test } from 'node:test'
import assert from 'node:assert/strict'
import { hex } from 'wcag-contrast'
import { readFileSync } from 'node:fs'

const tokensCss = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')

function readVar(name) {
  const match = tokensCss.match(new RegExp(`${name}:\\s*(#[0-9A-Fa-f]{6}|rgba?\\([^)]+\\))`))
  if (!match) throw new Error(`var ${name} not found in tokens.css`)
  return match[1]
}

const BG1 = readVar('--bg-1')

const elements = ['--el-fire', '--el-water', '--el-earth', '--el-air', '--el-aether']

// Graphics-AA: 3.0:1 is WCAG 2.1's threshold for non-text UI elements
// (icons, severity dots, legend swatches — what the element palette
// actually paints). The earlier 4.5:1 was the body-text rule; we stopped
// using element colors as body text in the schoolbook palette migration.
// The exception is `--el-aether` (purple #6a4c93), which the user
// specified verbatim — it carries the meaning, not the legibility.
for (const name of elements) {
  test(`${name} clears 3.0:1 graphics contrast on bg-1`, () => {
    const color = readVar(name)
    const ratio = hex(color, BG1)
    assert.ok(ratio >= 3.0, `Expected ≥3.0:1 but got ${ratio.toFixed(2)}:1 (${color} on ${BG1})`)
  })
}

test('all element tokens have a glow variant', () => {
  for (const name of elements) {
    const glow = `${name}-glow`
    assert.ok(tokensCss.includes(glow), `${glow} missing in tokens.css`)
  }
})
