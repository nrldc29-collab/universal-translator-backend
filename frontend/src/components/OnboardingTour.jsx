/**
 * OnboardingTour -- First-time user experience with guided tour
 * 
 * Features:
 * - Welcome message explaining core features
 * - Step-by-step guide through key UI elements
 * - Dismissible with "Don't show again" option
 * - Stored in localStorage for returning users
 */

import React, { useState, useEffect, useCallback } from 'react';
import { X, ArrowRight, Mic, Languages, MessageSquare, Sparkles } from 'lucide-react';

const TOUR_STEPS = [
  {
    key: 'welcome',
    icon: Sparkles,
    title: 'Welcome to Anai Translator',
    description: 'Hold the microphone button to speak, and your words will be translated instantly with beautiful, smooth audio.',
  },
  {
    key: 'mic',
    icon: Mic,
    title: 'Hold to Speak',
    description: 'Press and hold the large microphone button. Speak clearly, then release to translate.',
  },
  {
    key: 'languages',
    icon: Languages,
    title: 'Choose Languages',
    description: 'Select your target language from the buttons below. The app detects your source language automatically.',
  },
  {
    key: 'voice',
    icon: MessageSquare,
    title: 'Voice Assistant',
    description: 'Tap the 🎙 floating button to ask questions and hear answers out loud.',
  },
];

export default function OnboardingTour({ onComplete }) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  useEffect(() => {
    // Keep first launch focused on the translator; the tour can be enabled
    // deliberately for QA with localStorage.anai_onboarding_enabled = "true".
    const tourEnabled = localStorage.getItem('anai_onboarding_enabled') === 'true';
    const hasSeenTour = localStorage.getItem('anai_onboarding_seen');
    if (tourEnabled && !hasSeenTour) {
      setIsOpen(true);
    }
  }, []);

  const handleNext = useCallback(() => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  }, [currentStep]);

  const handleComplete = useCallback(() => {
    if (dontShowAgain) {
      localStorage.setItem('anai_onboarding_seen', 'true');
    }
    setIsOpen(false);
    onComplete?.();
  }, [dontShowAgain, onComplete]);

  const handleSkip = useCallback(() => {
    if (dontShowAgain) {
      localStorage.setItem('anai_onboarding_seen', 'true');
    }
    setIsOpen(false);
  }, [dontShowAgain]);

  if (!isOpen) return null;

  const step = TOUR_STEPS[currentStep];
  const StepIcon = step.icon;

  return (
    <div className="onboarding-overlay" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="onboarding-card">
        <button
          className="onboarding-close"
          onClick={handleSkip}
          aria-label="Skip tour"
        >
          <X size={20} strokeWidth={2} />
        </button>

        <div className="onboarding-content">
          <div className="onboarding-icon">
            <StepIcon size={48} strokeWidth={1.8} />
          </div>

          <h2 id="onboarding-title" className="onboarding-title">
            {step.title}
          </h2>

          <p className="onboarding-description">
            {step.description}
          </p>

          <div className="onboarding-progress">
            {TOUR_STEPS.map((_, idx) => (
              <span
                key={idx}
                className={`progress-dot ${idx === currentStep ? 'active' : ''}`}
                aria-label={`Step ${idx + 1} of ${TOUR_STEPS.length}`}
              />
            ))}
          </div>
        </div>

        <div className="onboarding-footer">
          <label className="dont-show-checkbox">
            <input
              type="checkbox"
              checked={dontShowAgain}
              onChange={(e) => setDontShowAgain(e.target.checked)}
            />
            <span>Don't show again</span>
          </label>

          <div className="onboarding-actions">
            <button
              className="onboarding-skip"
              onClick={handleSkip}
            >
              Skip
            </button>
            <button
              className="onboarding-next"
              onClick={handleNext}
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
