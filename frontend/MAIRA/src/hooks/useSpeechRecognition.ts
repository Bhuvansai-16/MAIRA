import { useState, useEffect, useCallback } from 'react';

// Types for the Web Speech API
interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start: () => void;
    stop: () => void;
    onstart: () => void;
    onresult: (event: SpeechRecognitionEvent) => void;
    onerror: (event: SpeechRecognitionErrorEvent) => void;
    onend: () => void;
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
    const [error, setError] = useState<string | null>(null);
    const [recognition, setRecognition] = useState<SpeechRecognition | null>(null);

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
                    if (onFinalTranscript) {
                        onFinalTranscript(finalText);
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

            setRecognition(recognitionInstance);
        } else {
            setError('Speech recognition not supported in this browser.');
        }
    }, []);

    const startListening = useCallback(() => {
        if (recognition) {
            try {
                setTranscript('');
                setFinalTranscript('');  // Reset final transcript
                setError(null);
                recognition.start();
            } catch (error) {
                console.error("Error starting speech recognition:", error);
                // If already started, stop and restart
                recognition.stop();
                setTimeout(() => {
                    try { recognition.start(); } catch (e) { console.error(e); }
                }, 200);
            }
        } else {
            setError("Speech recognition is not supported in this browser.");
        }
    }, [recognition]);

    const stopListening = useCallback(() => {
        if (recognition) {
            recognition.stop();
            setIsListening(false);
        }
    }, [recognition]);

    return { isListening, transcript, finalTranscript, error, startListening, stopListening, hasRecognition: !!recognition };
};
