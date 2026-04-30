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

for (const name of elements) {
  test(`${name} clears 4.5:1 contrast on bg-1`, () => {
    const color = readVar(name)
    const ratio = hex(color, BG1)
    assert.ok(ratio >= 4.5, `Expected ≥4.5:1 but got ${ratio.toFixed(2)}:1 (${color} on ${BG1})`)
  })
}

test('all element tokens have a glow variant', () => {
  for (const name of elements) {
    const glow = `${name}-glow`
    assert.ok(tokensCss.includes(glow), `${glow} missing in tokens.css`)
  }
})
