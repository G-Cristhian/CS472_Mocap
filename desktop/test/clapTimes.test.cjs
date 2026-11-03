// parseClapTimes, the clap-times box (node --test, after tsc -p tsconfig.main.json).
const test = require('node:test')
const assert = require('node:assert/strict')
const { parseClapTimes } = require('../dist/main/shared/clapTimes.js')

test('a blank box means find the claps from the audio', () => {
  assert.equal(parseClapTimes('', 3), null)
  assert.equal(parseClapTimes('   ', 3), null)
})

test('commas, semicolons and spaces all separate the times', () => {
  assert.deepEqual(parseClapTimes('1.25 0.80 1.10', 3), [1.25, 0.8, 1.1])
  assert.deepEqual(parseClapTimes('1.25, 0.80; 1.10', 3), [1.25, 0.8, 1.1])
  assert.deepEqual(parseClapTimes('  1.25,0.80  ', 2), [1.25, 0.8])
})

test('a stray comma is not a clap at 0 s (#105)', () => {
  assert.deepEqual(parseClapTimes('1.25, 0.80,', 2), [1.25, 0.8])
  assert.deepEqual(parseClapTimes(',1.25 0.80', 2), [1.25, 0.8])
  assert.deepEqual(parseClapTimes('1.25,,0.80', 2), [1.25, 0.8])
  // with three videos the same text is one time short, so it is refused
  assert.equal(parseClapTimes('1.25, 0.80,', 3), 'Give 3 clap times, one per video in camera order (got 2).')
})

test('a typed 0 is still a time', () => {
  assert.deepEqual(parseClapTimes('0 1.5', 2), [0, 1.5])
})

test('words, negative and endless numbers are refused', () => {
  const message = 'Clap times must be numbers of seconds, e.g. 1.25 0.80 1.10'
  assert.equal(parseClapTimes('1.25 abc', 2), message)
  assert.equal(parseClapTimes('1.25 -0.5', 2), message)
  assert.equal(parseClapTimes('1.25 1e999', 2), message)
})

test('a list of the wrong length is refused', () => {
  assert.equal(parseClapTimes('1.25 0.80 1.10', 2), 'Give 2 clap times, one per video in camera order (got 3).')
})
