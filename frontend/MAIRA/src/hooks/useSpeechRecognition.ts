import { useState, useEffect, useCallback, useRef } from 'react';

// Types for the Web Speech API
interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start: () => void;
    stop: () => void;
    abort: () => void;
    onstart: (() => void) | null;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
}

interface SpeechRecognitionEvent {
    results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
    [index: number]: SpeechRecognitionResult;
    length: number;
}

interface SpeechRecognitionResult {
    [index: number]: SpeechRecognitionAlternative;
    isFinal: boolean;
}

interface SpeechRecognitionAlternative {
    transcript: string;
}

interface SpeechRecognitionErrorEvent extends Event {
    error: string;
}

declare global {
    interface Window {
        SpeechRecognition: {
            new(): SpeechRecognition;
        };
        webkitSpeechRecognition: {
            new(): SpeechRecognition;
        };
    }
}

export const useSpeechRecognition = (onFinalTranscript?: (text: string) => void) => {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [finalTranscript, setFinalTranscript] = useState('');  // Only set when speech ends
    const [error, setError] = useState<string | null>(() => {
         if (typeof window !== 'undefined' && !(window.SpeechRecognition || window.webkitSpeechRecognition)) {
             return 'Speech recognition not supported in this browser.';
         }
         return null;
    });
    const [hasRecognition] = useState(() => {
        if (typeof window === 'undefined') return false;
        return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    });
    
    // Use refs for the recognition instance and callback to avoid re-renders/dependency loops
    const recognitionRef = useRef<SpeechRecognition | null>(null);
    const onFinalTranscriptRef = useRef(onFinalTranscript);

    // Update callback ref when it changes
    useEffect(() => {
        onFinalTranscriptRef.current = onFinalTranscript;
    }, [onFinalTranscript]);

    useEffect(() => {
        if (typeof window === 'undefined') return;

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (SpeechRecognition) {
            const recognitionInstance = new SpeechRecognition();
            recognitionInstance.continuous = false;
            recognitionInstance.interimResults = true;
            recognitionInstance.lang = 'en-US';

            recognitionInstance.onstart = () => {
                setError(null);
                setIsListening(true);
            };

            recognitionInstance.onresult = (event: SpeechRecognitionEvent) => {
                let currentTranscript = '';
                let finalText = '';
                for (let i = 0; i < event.results.length; i++) {
                    const result = event.results[i];
                    if (result.isFinal) {
                        finalText += result[0].transcript;
                    } else {
                        currentTranscript += result[0].transcript;
                    }
                }
                
                // Show interim results while listening
                setTranscript(currentTranscript || finalText);
                
                // If we have final text, save it
                if (finalText) {
                    setFinalTranscript(prev => prev + finalText);
                    if (onFinalTranscriptRef.current) {
                        onFinalTranscriptRef.current(finalText);
                    }
                }
            };

            recognitionInstance.onerror = (event: SpeechRecognitionErrorEvent) => {
                console.error('Speech recognition error', event.error);
                if (event.error === 'not-allowed') {
                    setError('Microphone access denied. Please allow permissions.');
                } else if (event.error === 'no-speech') {
                    setError('No speech detected. Please try again.');
                } else {
                    setError(`Error: ${event.error}`);
                }
                setIsListening(false);
            };

            recognitionInstance.onend = () => {
                setIsListening(false);
            };

            recognitionRef.current = recognitionInstance;
        }

        // Cleanup function
        return () => {
            if (recognitionRef.current) {
                // Remove listeners to prevent state updates after unmount
                recognitionRef.current.onstart = null;
                recognitionRef.current.onresult = null;
                recognitionRef.current.onerror = null;
                recognitionRef.current.onend = null;
                try {
                    recognitionRef.current.abort();
                } catch {
                    // Ignore abort errors
                }
            }
        };
    }, []); // Run once on mount

    const startListening = useCallback(() => {
        if (recognitionRef.current) {
            try {
                setTranscript('');
                setFinalTranscript('');  // Reset final transcript
                setError(null);
                recognitionRef.current.start();
            } catch (error) {
                console.error("Error starting speech recognition:", error);
                
                // Attempt to reset/restart if it's a state error
                try {
                   recognitionRef.current.stop();
                   setTimeout(() => {
                       if (recognitionRef.current) recognitionRef.current.start();
                   }, 100);
                } catch (retryError) {
                    console.error("Failed to restart recognition:", retryError);
                }
            }
        }
    }, []);

    const stopListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
        }
    }, []);

    const resetTranscript = useCallback(() => {
        setTranscript('');
        setFinalTranscript('');
    }, []);

    return {
        isListening,
        transcript,
        finalTranscript,
        error,
        startListening,
        stopListening,
        resetTranscript,
        hasRecognition
    };
};
