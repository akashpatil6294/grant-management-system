import { describe, it, expect } from 'vitest';
import { money, subtract } from './money';
describe('decimal money', () => {
  it('subtracts without binary rounding artifacts', () => { expect(subtract('0.30','0.10')).toBe('0.20'); });
  it('formats large values without losing cents', () => { expect(money('999999999999.99','INR')).toBe('INR 999,999,999,999.99'); });
  it('formats negative differences', () => { expect(money(subtract('0','0.01'),'USD')).toBe('USD -0.01'); });
});
