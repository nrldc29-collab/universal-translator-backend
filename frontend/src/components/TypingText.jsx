/**
 * TypingText -- Displays text appearing word by word with smooth animations
 * Perfect for showing translations as they arrive from the backend
 */

import React, { useState, useEffect, useRef } from 'react';

export default function TypingText({
  text = '',
  isActive = false,
  typingSpeed = 30,
  className = '',
  onComplete,
  highlightWords = false,
  languageCode = '',
}) {
  const [displayedText, setDisplayedText] = useState('');
  const [currentWordIndex, setCurrentWordIndex] = useState(0);
  const wordsRef = useRef([]);
  const timeoutRef = useRef(null);

  useEffect(() => {
    // Split text into words (preserving punctuation)
    wordsRef.current = text.match(/[^\s]+/g) || [];
    
    if (!isActive || wordsRef.current.length === 0) {
      setDisplayedText(text);
      setCurrentWordIndex(wordsRef.current.length);
      return;
    }

    // Reset when text changes
    setDisplayedText('');
    setCurrentWordIndex(0);

    const typeNextWord = (index) => {
      if (index >= wordsRef.current.length) {
        onComplete?.();
        return;
      }

      const wordsToShow = wordsRef.current.slice(0, index + 1);
      setDisplayedText(wordsToShow.join(' '));
      setCurrentWordIndex(index + 1);

      // Calculate delay based on word length (shorter words = faster)
      const word = wordsRef.current[index];
      const delay = Math.max(typingSpeed, word.length * typingSpeed * 0.3);

      timeoutRef.current = setTimeout(() => {
        typeNextWord(index + 1);
      }, delay);
    };

    // Start typing
    timeoutRef.current = setTimeout(() => {
      typeNextWord(0);
    }, 50);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [text, isActive, typingSpeed, onComplete]);

  // If not active, show full text immediately
  if (!isActive) {
    return (
      <span className={`typing-text ${className}`}>
        {text}
        {text && <span className="cursor blink" />}
      </span>
    );
  }

  const renderWords = () => {
    if (!highlightWords) {
      return (
        <>
          {displayedText}
          {currentWordIndex < wordsRef.current.length && (
            <span className="cursor typing" />
          )}
        </>
      );
    }

    // Render with individual word highlighting
    return wordsRef.current.map((word, index) => {
      const isTyped = index < currentWordIndex;
      const isCurrent = index === currentWordIndex;
      
      if (!isTyped && !isCurrent) return null;

      return (
        <span
          key={index}
          className={`word ${isCurrent ? 'current' : ''} ${isTyped ? 'typed' : ''}`}
          style={{ '--word-index': index }}
        >
          {word}
          {index < wordsRef.current.length - 1 ? ' ' : ''}
          {isCurrent && <span className="cursor typing" />}
        </span>
      );
    });
  };

  return (
    <span 
      className={`typing-text active ${className}`}
      lang={languageCode}
      dir={['ar', 'he', 'ur'].includes(languageCode) ? 'rtl' : 'ltr'}
    >
      {renderWords()}
    </span>
  );
}
