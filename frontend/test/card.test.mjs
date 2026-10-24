import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
const code = await readFile(new URL('../src/t2c_clermont-ferrand_card.js', import.meta.url), 'utf8');
function environment() {
  const registry = new Map();
  const window = {};
  const context = vm.createContext({window, HTMLElement: class {}, console: {info() {}},
    customElements: {get: key => registry.get(key), define: (key, value) => {
      assert.ok(!registry.has(key)); registry.set(key, value);
    }}, document: {createElement: tag => ({tag})}});
  return {registry, window, context};
}
test('same module evaluated twice registers card and editor exactly once', () => {
  const env = environment();
  vm.runInContext(code, env.context);
  const first = env.registry.get('t2c-clermontferrand-card');
  vm.runInContext(code, env.context);
  assert.equal(env.registry.size, 2);
  assert.equal(env.registry.get('t2c-clermontferrand-card'), first);
  assert.equal(env.window.customCards.length, 1);
  assert.equal(env.window.customCards[0].type, 't2c-clermontferrand-card');
});
test('an existing legacy component is never redefined', () => {
  const env = environment();
  const legacy = class {};
  env.registry.set('t2c-clermontferrand-card', legacy);
  vm.runInContext(code, env.context);
  assert.equal(env.registry.get('t2c-clermontferrand-card'), legacy);
  assert.equal(env.registry.size, 1);
});
test('editor, config defaults, realtime and route display stay compatible', () => {
  const env = environment(); vm.runInContext(code, env.context);
  const Card = env.registry.get('t2c-clermontferrand-card');
  assert.equal(Card.getConfigElement().tag, 't2c-clermontferrand-card-editor');
  const card = new Card();
  card.setConfig({entity: 'sensor.test_passage_1', title: 'Test', passages: 6, show_network_info: true});
  assert.equal(card._getPassageEntity(3), 'sensor.test_passage_3');
  assert.equal(card.config.title, 'Test');
  assert.equal(card.config.passages, 6);
  assert.equal(card.config.show_network_info, true);
  assert.equal(card._isRealtime({state: '3 min', attributes: {realtime: true}}), true);
  assert.equal(card._isRealtime({state: '*12:00', attributes: {realtime: true}}), false);
  assert.equal(card._isRealtime({state: '12:00', attributes: {theoretical: true}}), false);
  const route = card._getRouteDisplay({attributes: {line: 'B', route_color: '0069b4'}}, '');
  assert.equal(route.label, 'B'); assert.equal(route.color, '#0069b4');
});
