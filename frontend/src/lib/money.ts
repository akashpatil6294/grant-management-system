import Decimal from 'decimal.js';
export const subtract = (left: string, right: string) => new Decimal(left).minus(right).toFixed(2);
export function money(amount: string, currency: string) {
  // Format the decimal string without first converting money to floating point.
  const [whole, fraction] = new Decimal(amount).toFixed(2).split('.');
  return `${currency} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction}`;
}
