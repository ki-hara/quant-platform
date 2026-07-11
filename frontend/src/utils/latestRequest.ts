export class LatestRequest {
  private current: AbortController | null = null;

  start(): AbortController {
    this.current?.abort();
    const controller = new AbortController();
    this.current = controller;
    return controller;
  }

  isCurrent(controller: AbortController): boolean {
    return this.current === controller && !controller.signal.aborted;
  }

  finish(controller: AbortController): void {
    if (this.current === controller) this.current = null;
  }

  cancel(): void {
    this.current?.abort();
    this.current = null;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
