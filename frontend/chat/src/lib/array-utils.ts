
/**
 * Utility functions for safe array operations
 * Helps prevent "Cannot read properties of undefined (reading 'filter')" errors
 * especially in cross-platform environments
 */

/**
 * Ensures the input is always a valid array
 * @param input - Any input that should be an array
 * @returns A valid array
 */
export function ensureArray<T>(input: T[] | undefined | null | any): T[] {
  if (Array.isArray(input)) {
    return input;
  }
  
  // Log warning for debugging in development
  if (process.env.NODE_ENV === 'development' && input !== undefined && input !== null) {
    console.warn('ensureArray: Expected array but received:', typeof input, input);
  }
  
  return [];
}

/**
 * Safe filter operation that ensures the input is an array
 * @param input - Input that should be an array
 * @param predicate - Filter predicate function
 * @returns Filtered array
 */
export function safeFilter<T>(
  input: T[] | undefined | null | any,
  predicate: (value: T, index: number, array: T[]) => boolean
): T[] {
  const safeArray = ensureArray<T>(input);
  return safeArray.filter(predicate);
}

/**
 * Safe map operation that ensures the input is an array
 * @param input - Input that should be an array
 * @param mapper - Map function
 * @returns Mapped array
 */
export function safeMap<T, U>(
  input: T[] | undefined | null | any,
  mapper: (value: T, index: number, array: T[]) => U
): U[] {
  const safeArray = ensureArray<T>(input);
  return safeArray.map(mapper);
}

/**
 * Safe find operation that ensures the input is an array
 * @param input - Input that should be an array
 * @param predicate - Find predicate function
 * @returns Found element or undefined
 */
export function safeFind<T>(
  input: T[] | undefined | null | any,
  predicate: (value: T, index: number, array: T[]) => boolean
): T | undefined {
  const safeArray = ensureArray<T>(input);
  return safeArray.find(predicate);
}

/**
 * Safe length check that ensures the input is an array
 * @param input - Input that should be an array
 * @returns Array length
 */
export function safeLength(input: any[] | undefined | null | any): number {
  const safeArray = ensureArray(input);
  return safeArray.length;
}
