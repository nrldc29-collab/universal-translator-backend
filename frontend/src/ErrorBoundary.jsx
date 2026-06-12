import React from 'react';
import { AlertTriangle } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo,
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="eb-screen">
          <div className="eb-card">
            <div className="eb-icon" aria-hidden="true">
              <AlertTriangle size={36} strokeWidth={1.8} />
            </div>
            <h1 className="eb-title">Something went wrong</h1>
            <p className="eb-body">
              The conversation bridge hit an unexpected error. Try refreshing the page or resetting the app state.
            </p>
            <div className="eb-actions">
              <button type="button" className="eb-btn primary" onClick={this.handleReset}>
                Reset App
              </button>
              <button type="button" className="eb-btn secondary" onClick={() => window.location.reload()}>
                Refresh Page
              </button>
            </div>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="eb-details">
                <summary className="eb-summary">Error Details (Development Only)</summary>
                <pre className="eb-pre">
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
