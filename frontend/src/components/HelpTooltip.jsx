/**
 * HelpTooltip -- Accessible help tooltips with keyboard navigation
 * 
 * Features:
 * - Keyboard accessible (Tab, Enter, Escape)
 * - ARIA attributes for screen readers
 * - Multiple positions (top, bottom, left, right)
 * - Dismissible with click or Escape
 */

import React, { useState, useRef, useEffect } from 'react';
import { HelpCircle, X } from 'lucide-react';

export default function HelpTooltip({ 
  children, 
  content, 
  position = 'top',
  title = 'Help',
}) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);

  const handleToggle = () => setIsOpen(!isOpen);
  const handleClose = () => setIsOpen(false);

  // Handle keyboard navigation
  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      handleClose();
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleToggle();
    }
  };

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        tooltipRef.current &&
        !tooltipRef.current.contains(event.target) &&
        triggerRef.current &&
        !triggerRef.current.contains(event.target)
      ) {
        handleClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const positionStyles = {
    top: { bottom: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
    bottom: { top: 'calc(100% + 8px)', left: '50%', transform: 'translateX(-50%)' },
    left: { right: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
    right: { left: 'calc(100% + 8px)', top: '50%', transform: 'translateY(-50%)' },
  };

  const arrowStyles = {
    top: { bottom: '-6px', left: '50%', transform: 'translateX(-50%) rotate(180deg)' },
    bottom: { top: '-6px', left: '50%', transform: 'translateX(-50%)' },
    left: { right: '-6px', top: '50%', transform: 'translateY(-50%) rotate(90deg)' },
    right: { left: '-6px', top: '50%', transform: 'translateY(-50%) rotate(-90deg)' },
  };

  return (
    <div className="help-tooltip-container">
      <button
        ref={triggerRef}
        className="help-tooltip-trigger"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-label={`${title} - ${content}`}
        type="button"
      >
        <HelpCircle size={16} strokeWidth={2} />
      </button>

      {isOpen && (
        <div
          ref={tooltipRef}
          className="help-tooltip-content"
          style={positionStyles[position]}
          role="tooltip"
          aria-label={title}
        >
          <div className="help-tooltip-header">
            <strong>{title}</strong>
            <button
              className="help-tooltip-close"
              onClick={handleClose}
              aria-label="Close help"
              type="button"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>
          <div className="help-tooltip-body">
            {content}
          </div>
          <div
            className="help-tooltip-arrow"
            style={arrowStyles[position]}
            aria-hidden="true"
          />
        </div>
      )}

    </div>
  );
}
