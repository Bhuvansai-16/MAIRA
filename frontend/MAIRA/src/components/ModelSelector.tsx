import { useState, useEffect, useRef } from 'react';
import { ChevronDown, Check, Sparkles, Zap, Brain } from 'lucide-react';
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

// Provider icon components
const ProviderIcon = ({ provider, className }: { provider: string; className?: string }) => {
    switch (provider) {
        case 'gemini':
        case 'google':
            return (
                <div className={cn("flex items-center justify-center rounded-lg bg-blue-500/20", className)}>
                    <Sparkles size={14} className="text-blue-400" />
                </div>
            );
        case 'anthropic':
            return (
                <div className={cn("flex items-center justify-center rounded-lg bg-orange-500/20", className)}>
                    <span className="text-orange-400 font-bold text-xs">A</span>
                </div>
            );
        case 'openai':
        case 'groq':
            return (
                <div className={cn("flex items-center justify-center rounded-lg bg-green-500/20", className)}>
                    <Brain size={14} className="text-green-400" />
                </div>
            );
        default:
            return (
                <div className={cn("flex items-center justify-center rounded-lg bg-neutral-500/20", className)}>
                    <Zap size={14} className="text-neutral-400" />
                </div>
            );
    }
};

// Category order for display
const CATEGORY_ORDER = [
    'Fast and cost-efficient',
    'Versatile and highly intelligent',
    'Most powerful at complex tasks'
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
    'Fast and cost-efficient': <Zap size={12} className="text-yellow-400" />,
    'Versatile and highly intelligent': <Sparkles size={12} className="text-blue-400" />,
    'Most powerful at complex tasks': <Brain size={12} className="text-purple-400" />
};

export const ModelSelector = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [models, setModels] = useState<Record<string, Model[]>>({});
    const [currentModel, setCurrentModel] = useState<ModelsResponse['current'] | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isChanging, setIsChanging] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Fetch available models on mount
    useEffect(() => {
        fetchModels();
    }, []);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

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

    // Sort categories by predefined order
    const sortedCategories = CATEGORY_ORDER.filter(cat => models[cat]);

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                disabled={isLoading || isChanging}
                className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all",
                    "bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20",
                    isOpen && "bg-white/10 border-white/20",
                    (isLoading || isChanging) && "opacity-50 cursor-wait"
                )}
            >
                {currentModel && (
                    <ProviderIcon provider={currentModel.icon} className="h-5 w-5" />
                )}
                <span className="text-[10px] font-bold text-neutral-300 uppercase tracking-wider max-w-[100px] truncate">
                    {isChanging ? 'Switching...' : (currentModel?.name || 'Select Model')}
                </span>
                <ChevronDown 
                    size={12} 
                    className={cn(
                        "text-neutral-500 transition-transform",
                        isOpen && "rotate-180"
                    )} 
                />
            </button>

            {/* Dropdown Panel */}
            {isOpen && (
                <div className="absolute right-0 top-full mt-2 w-72 rounded-2xl bg-[#1a1a1a] border border-white/10 shadow-2xl shadow-black/50 overflow-hidden z-50 animate-fade-in">
                    {/* Header */}
                    <div className="px-4 py-3 border-b border-white/5">
                        <h3 className="text-sm font-bold text-white">Models</h3>
                    </div>

                    {/* Model List */}
                    <div className="max-h-[400px] overflow-y-auto">
                        {sortedCategories.map((category) => (
                            <div key={category}>
                                {/* Category Header */}
                                <div className="px-4 py-2 bg-white/5 flex items-center gap-2">
                                    {CATEGORY_ICONS[category]}
                                    <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider">
                                        {category}
                                    </span>
                                </div>

                                {/* Models in Category */}
                                {models[category]?.map((model) => {
                                    const isSelected = model.key === currentModel?.key;
                                    
                                    return (
                                        <button
                                            key={model.key}
                                            onClick={() => selectModel(model.key)}
                                            className={cn(
                                                "w-full flex items-center gap-3 px-4 py-3 transition-all",
                                                "hover:bg-white/5",
                                                isSelected && "bg-blue-500/10"
                                            )}
                                        >
                                            <ProviderIcon provider={model.icon} className="h-8 w-8" />
                                            <div className="flex-1 text-left">
                                                <div className={cn(
                                                    "text-sm font-semibold",
                                                    isSelected ? "text-blue-400" : "text-white"
                                                )}>
                                                    {model.name}
                                                </div>
                                            </div>
                                            {isSelected && (
                                                <Check size={16} className="text-blue-400" />
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
