import '@testing-library/jest-dom';

if (!globalThis.crypto) {
  // @ts-ignore
  globalThis.crypto = {};
}

if (!globalThis.crypto.randomUUID) {
  // @ts-ignore
  globalThis.crypto.randomUUID = () => '00000000-0000-4000-8000-000000000001';
}
