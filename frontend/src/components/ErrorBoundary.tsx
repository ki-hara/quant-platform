import { Component, ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="login-shell">
          <section className="login-panel">
            <div>
              <p className="eyebrow">오류</p>
              <h1>화면을 표시하지 못했습니다</h1>
              <p className="login-copy">{this.state.error.message}</p>
            </div>
            <button type="button" onClick={() => window.location.reload()}>
              새로고침
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
