import { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '../lib/utils';

const API_BASE = 'http://localhost:8000';

interface Model {
    key: string;
    name: string;
    provider: string;
    icon: string;
}

interface ModelsResponse {
    models: Record<string, Model[]>;
    current: {
        key: string;
        name: string;
        provider: string;
        category: string;
        icon: string;
    };
}

// Category order for display
const CATEGORY_ORDER = [
    'Fast and cost-efficient',
    'Versatile and highly intelligent',
    'Most powerful at complex tasks'
];

export const ModelSelector = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [models, setModels] = useState<Record<string, Model[]>>({});
    const [currentModel, setCurrentModel] = useState<ModelsResponse['current'] | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isChanging, setIsChanging] = useState(false);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const [dropdownPos, setDropdownPos] = useState({ bottom: 0, left: 0 });

    // Fetch available models on mount
    useEffect(() => {
        fetchModels();
    }, []);

    // Calculate position
    const updatePos = useCallback(() => {
        if (triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setDropdownPos({
                bottom: window.innerHeight - rect.top + 8, // 8px gap above button
                left: rect.left
            });
        }
    }, []);

    // Recalculate on open & events
    useEffect(() => {
        if (!isOpen) return;
        updatePos();
        window.addEventListener("scroll", updatePos, true);
        window.addEventListener("resize", updatePos);
        return () => {
            window.removeEventListener("scroll", updatePos, true);
            window.removeEventListener("resize", updatePos);
        };
    }, [isOpen, updatePos]);

    // Close dropdown when clicking outside
    useEffect(() => {
        if (!isOpen) return;
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as Node;
            if (
                triggerRef.current && !triggerRef.current.contains(target) &&
                dropdownRef.current && !dropdownRef.current.contains(target)
            ) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen]);

    const fetchModels = async () => {
        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE}/models`);
            if (response.ok) {
                const data: ModelsResponse = await response.json();
                setModels(data.models);
                setCurrentModel(data.current);
            }
        } catch (error) {
            console.error('Failed to fetch models:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const selectModel = async (modelKey: string) => {
        if (modelKey === currentModel?.key) {
            setIsOpen(false);
            return;
        }

        setIsChanging(true);
        try {
            const response = await fetch(`${API_BASE}/models/select`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_key: modelKey })
            });

            if (response.ok) {
                const data = await response.json();
                setCurrentModel(data.current);
                setIsOpen(false);
            } else {
                console.error('Failed to select model');
            }
        } catch (error) {
            console.error('Failed to select model:', error);
        } finally {
            setIsChanging(false);
        }
    };

    // Sort and flatten models for display
    const flatModels = CATEGORY_ORDER.flatMap(cat => models[cat] || []);

    const dropdown = isOpen && createPortal(
        <div
            ref={dropdownRef}
            className="fixed z-[200] w-[200px] rounded-xl bg-[#0a0a0a] border border-white/10 shadow-2xl shadow-black/80 overflow-hidden animate-slide-up"
            style={{
                bottom: dropdownPos.bottom,
                left: dropdownPos.left,
            }}
        >
            <div className="p-1.5 flex flex-col gap-0.5 max-h-[300px] overflow-y-auto scrollbar-hide">
                {flatModels.map((model) => {
                    const isSelected = model.key === currentModel?.key;

                    return (
                        <button
                            key={model.key}
                            onClick={() => selectModel(model.key)}
                            className={cn(
                                "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm text-left transition-all",
                                isSelected
                                    ? "bg-indigo-500 text-white font-medium"
                                    : "text-neutral-300 hover:bg-white/5 hover:text-white"
                            )}
                        >
                            <span>{model.name}</span>
                            {isSelected && <Check size={14} className="text-white" />}
                        </button>
                    );
                })}
            </div>
        </div>,
        document.body
    );

    return (
        <>
            {/* Trigger Button */}
            <button
                ref={triggerRef}
                onClick={() => setIsOpen(!isOpen)}
                disabled={isLoading || isChanging}
                className={cn(
                    "flex items-center gap-1.5 text-sm font-medium text-neutral-300 transition-colors hover:text-white",
                    (isLoading || isChanging) && "opacity-50 cursor-wait"
                )}
            >
                <span>
                    {isChanging ? 'Switching...' : (currentModel?.name || 'Select Model')}
                </span>
                <ChevronDown
                    size={14}
                    className={cn(
                        "text-neutral-500 transition-transform duration-200",
                        isOpen && "rotate-180"
                    )}
                />
            </button>
            {dropdown}
        </>
    );
};
