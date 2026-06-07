/**
 * OnboardingTour -- First-time user experience with guided tour
 */

import React, { useState, useEffect, useCallback, useLayoutEffect } from 'react';
import { X, ArrowRight, ArrowLeft, Mic, Languages, Settings2, Sparkles } from 'lucide-react';

export const ONBOARDING_OPEN_EVENT = 'anai-open-onboarding';

const TOUR_TARGETS = {
  welcome: null,
  mic: '[data-tour-target="mic"]',
  languages: '[data-tour-target="languages"]',
  settings: '[data-tour-target="settings"]',
};

const TOUR_STEPS = [
  {
    key: 'welcome',
    icon: Sparkles,
    title: 'Welcome to Anai Translator',
    description: 'Speak in one language and hear a natural translation instantly. Works in your browser and on your phone.',
    spotlightHint: 'You are in the right place — setup takes less than a minute.',
  },
  {
    key: 'mic',
    icon: Mic,
    title: 'Tap to speak',
    description: 'Tap the microphone to speak, or use the Type button to enter text. Anai translates and plays the result out loud.',
    spotlightHint: 'Look for the large mic button in the center of the screen.',
  },
  {
    key: 'languages',
    icon: Languages,
    title: 'Pick your languages',
    description: 'Use the language bar to choose source and target. Tap Flip to swap direction anytime.',
    spotlightHint: 'Language chips sit just above the mic — tap either side to change.',
  },
  {
    key: 'settings',
    icon: Settings2,
    title: 'Tune your experience',
    description: 'Open Settings for volume, conversation history, and advanced options. Tap the help icon anytime to replay this tour.',
    spotlightHint: 'The gear icon in the header opens volume, history, and more.',
  },
];

export default function OnboardingTour({ onComplete }) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const [spotlightRect, setSpotlightRect] = useState(null);

  const openTour = useCallback((step = 0) => {
    setCurrentStep(step);
    setIsOpen(true);
  }, []);

  useEffect(() => {
    const hasSeenTour = localStorage.getItem('anai_onboarding_seen');
    if (!hasSeenTour) {
      openTour(0);
    }
  }, [openTour]);

  useEffect(() => {
    const handler = () => openTour(0);
    window.addEventListener(ONBOARDING_OPEN_EVENT, handler);
    return () => window.removeEventListener(ONBOARDING_OPEN_EVENT, handler);
  }, [openTour]);

  const handleComplete = useCallback(() => {
    localStorage.setItem('anai_onboarding_seen', 'true');
    setIsOpen(false);
    onComplete?.();
  }, [onComplete]);

  const handleNext = useCallback(() => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  }, [currentStep, handleComplete]);

  const handleBack = useCallback(() => {
    if (currentStep > 0) setCurrentStep(currentStep - 1);
  }, [currentStep]);

  const handleSkip = useCallback(() => {
    localStorage.setItem('anai_onboarding_seen', 'true');
    setIsOpen(false);
  }, []);

  const step = TOUR_STEPS[currentStep];

  useLayoutEffect(() => {
    if (!isOpen) {
      setSpotlightRect(null);
      return undefined;
    }

    const selector = TOUR_TARGETS[step.key];
    if (!selector) {
      setSpotlightRect(null);
      return undefined;
    }

    const updateSpotlight = () => {
      const el = document.querySelector(selector);
      if (!el) {
        setSpotlightRect(null);
        return;
      }
      el.classList.add('tour-highlight');
      const rect = el.getBoundingClientRect();
      const pad = 10;
      setSpotlightRect({
        top: Math.max(8, rect.top - pad),
        left: Math.max(8, rect.left - pad),
        width: Math.min(window.innerWidth - 16, rect.width + pad * 2),
        height: rect.height + pad * 2,
      });
    };

    updateSpotlight();
    const t = window.setTimeout(updateSpotlight, 80);
    window.addEventListener('resize', updateSpotlight);
    window.addEventListener('scroll', updateSpotlight, true);

    return () => {
      window.clearTimeout(t);
      window.removeEventListener('resize', updateSpotlight);
      window.removeEventListener('scroll', updateSpotlight, true);
      document.querySelectorAll('.tour-highlight').forEach((node) => node.classList.remove('tour-highlight'));
    };
  }, [isOpen, step.key]);

  if (!isOpen) return null;

  const StepIcon = step.icon;
  const hasSpotlight = Boolean(spotlightRect);

  return (
    <div
      className={`onboarding-overlay${hasSpotlight ? ' has-spotlight' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      {hasSpotlight && (
        <div
          className="onboarding-spotlight-ring"
          style={{
            '--spot-top': `${spotlightRect.top}px`,
            '--spot-left': `${spotlightRect.left}px`,
            '--spot-width': `${spotlightRect.width}px`,
            '--spot-height': `${spotlightRect.height}px`,
          }}
          aria-hidden="true"
        />
      )}
      <div className="onboarding-card">
        <button
          className="onboarding-close"
          onClick={handleSkip}
          aria-label="Skip tour"
          type="button"
        >
          <X size={20} strokeWidth={2} />
        </button>

        <div className="onboarding-content" key={step.key}>
          <div className="onboarding-icon">
            <StepIcon size={48} strokeWidth={1.8} />
          </div>

          <h2 id="onboarding-title" className="onboarding-title">
            {step.title}
          </h2>

          <p className="onboarding-description">
            {step.description}
          </p>

          {step.spotlightHint ? (
            <p className="onboarding-spotlight">
              <span className="onboarding-spotlight-label">Tip</span>
              {step.spotlightHint}
            </p>
          ) : null}

          <p className="onboarding-step-counter" aria-live="polite">
            Step {currentStep + 1} of {TOUR_STEPS.length}
          </p>

          <div className="onboarding-progress">
            {TOUR_STEPS.map((_, idx) => (
              <span
                key={idx}
                className={`progress-dot ${idx === currentStep ? 'active' : ''} ${idx < currentStep ? 'done' : ''}`}
                aria-hidden="true"
              />
            ))}
          </div>
        </div>

        <div className="onboarding-footer">
          <p className="onboarding-keyboard-hint">
            On desktop: press <kbd>?</kbd> anytime for keyboard shortcuts
          </p>
          <label className="dont-show-checkbox">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don&apos;t show again</span>
          </label>

          <div className="onboarding-actions">
            {currentStep > 0 ? (
              <button
                className="onboarding-back"
                onClick={handleBack}
                type="button"
              >
                <ArrowLeft size={16} strokeWidth={2.5} />
                Back
              </button>
            ) : (
              <button
                className="onboarding-skip"
                onClick={handleSkip}
                type="button"
              >
                Skip
              </button>
            )}
            <button
              className="onboarding-next"
              onClick={handleNext}
              type="button"
            >
              {currentStep === TOUR_STEPS.length - 1 ? 'Get Started' : 'Next'}
              <ArrowRight size={16} strokeWidth={2.5} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
