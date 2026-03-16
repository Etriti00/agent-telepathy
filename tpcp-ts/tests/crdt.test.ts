import { LWWMap } from '../src/memory/crdt';

describe('LWWMap', () => {
  test('set and get returns value', () => {
    const map = new LWWMap('node-1');
    map.set('key1', 'value1');
    expect(map.get('key1')).toBe('value1');
  });

  test('last-writer-wins with higher timestamp', () => {
    const map = new LWWMap('node-1');
    map.set('key1', 'old');
    map.set('key1', 'new');
    expect(map.get('key1')).toBe('new');
  });

  test('get returns null for unknown key', () => {
    const map = new LWWMap('node-1');
    expect(map.get('missing')).toBeNull();
  });

  test('toDict returns all current values', () => {
    const map = new LWWMap('node-1');
    map.set('a', 1);
    map.set('b', 2);
    expect(map.toDict()).toEqual({ a: 1, b: 2 });
  });

  test('merge applies remote state with higher timestamp', () => {
    const local = new LWWMap('node-1');
    local.set('key1', 'local-value');

    const remote = new LWWMap('node-2');
    remote.set('key1', 'remote-value');

    // Serialize remote state and merge into local using an explicit future timestamp
    // so it will win regardless of local clock order.
    local.merge({ key1: { value: 'remote-wins', timestamp: 9999, writer_id: 'node-2' } });
    expect(local.get('key1')).toBe('remote-wins');
  });

  test('merge does not overwrite with older timestamp', () => {
    const map = new LWWMap('node-1');
    map.set('key1', 'current');

    // Attempt to merge a stale value with timestamp 0 — should be ignored.
    map.merge({ key1: { value: 'stale', timestamp: 0, writer_id: 'node-2' } });
    expect(map.get('key1')).toBe('current');
  });

  test('serializeState round-trips through merge', () => {
    const source = new LWWMap('node-A');
    source.set('x', 42);
    source.set('y', 'hello');

    const target = new LWWMap('node-B');
    target.merge(source.serializeState());

    expect(target.get('x')).toBe(42);
    expect(target.get('y')).toBe('hello');
  });

  test('logicalClock increments on each local set', () => {
    const map = new LWWMap('node-1');
    expect(map.logicalClock).toBe(0);
    map.set('a', 1);
    expect(map.logicalClock).toBe(1);
    map.set('b', 2);
    expect(map.logicalClock).toBe(2);
  });
});
