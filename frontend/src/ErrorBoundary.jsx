import React from 'react';

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
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          backgroundColor: '#03050a',
          color: '#f8fafc',
          fontFamily: 'system-ui, sans-serif',
        }}>
          <div style={{
            maxWidth: '520px',
            width: '100%',
            padding: '32px',
            borderRadius: '24px',
            backgroundColor: '#07111f',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.35)',
          }}>
            <h1 style={{
              fontSize: '24px',
              fontWeight: '900',
              color: '#fca5a5',
              marginBottom: '16px',
              marginTop: '0',
            }}>
              Something went wrong
            </h1>
            <p style={{
              fontSize: '14px',
              color: '#94a3b8',
              marginBottom: '24px',
              lineHeight: '1.6',
            }}>
              The translator encountered an unexpected error. You can try refreshing the page or resetting the app state.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              flexWrap: 'wrap',
            }}>
              <button
                onClick={this.handleReset}
                style={{
                  flex: '1',
                  minWidth: '140px',
                  padding: '12px 24px',
                  borderRadius: '999px',
                  border: 'none',
                  backgroundColor: 'linear-gradient(135deg, #67e8f9, #2dd4bf)',
                  color: '#03050a',
                  fontWeight: '800',
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'transform 0.2s',
                }}
                onMouseDown={(e) => e.target.style.transform = 'scale(0.98)'}
                onMouseUp={(e) => e.target.style.transform = 'scale(1)'}
              >
                Reset App
              </button>
              <button
                onClick={() => window.location.reload()}
                style={{
                  flex: '1',
                  minWidth: '140px',
                  padding: '12px 24px',
                  borderRadius: '999px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  backgroundColor: 'transparent',
                  color: '#e5ecff',
                  fontWeight: '800',
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'transform 0.2s',
                }}
                onMouseDown={(e) => e.target.style.transform = 'scale(0.98)'}
                onMouseUp={(e) => e.target.style.transform = 'scale(1)'}
              >
                Refresh Page
              </button>
            </div>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details style={{
                marginTop: '24px',
                padding: '16px',
                borderRadius: '12px',
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                fontSize: '12px',
                fontFamily: 'monospace',
                color: '#fca5a5',
                overflow: 'auto',
                maxHeight: '200px',
              }}>
                <summary style={{ cursor: 'pointer', marginBottom: '8px', color: '#f87171' }}>
                  Error Details (Development Only)
                </summary>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
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
