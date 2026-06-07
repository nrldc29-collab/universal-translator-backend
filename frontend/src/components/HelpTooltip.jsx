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
          data-position={position}
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
            data-position={position}
            aria-hidden="true"
          />
        </div>
      )}

    </div>
  );
}
