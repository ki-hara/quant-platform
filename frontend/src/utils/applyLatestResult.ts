import { isAbortError } from "./latestRequest";

export async function applyLatestResult<T>(
  request: Promise<T>, isCurrent: () => boolean,
  update: (value: T) => void, fail: (error: unknown) => void,
): Promise<void> {
  try {
    const value = await request;
    if (isCurrent()) update(value);
  } catch (error) {
    if (isCurrent() && !isAbortError(error)) fail(error);
  }
}
