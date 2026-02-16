import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { User, GraduationCap, Microscope, ChevronDown, Check, Plus, X, Trash2, Sparkles } from "lucide-react";
import { cn } from "../lib/utils";

export interface CustomPersona {
    persona_id: string;
    name: string;
    instructions: string;
    created_at?: string;
}

interface PersonaDropdownProps {
    persona: string;
    setPersona: (persona: string) => void;
    customPersonas: CustomPersona[];
    onAddPersona: (name: string, instructions: string) => Promise<void>;
    onDeletePersona: (personaId: string) => Promise<void>;
}

const BUILT_IN_PERSONAS = [
    { id: "default", label: "Default", icon: User, description: "Balanced research assistant" },
    { id: "student", label: "Student", icon: User, description: "Simple, clear explanations" },
    { id: "professor", label: "Professor", icon: GraduationCap, description: "Academic & authoritative" },
    { id: "researcher", label: "Researcher", icon: Microscope, description: "Technical & data-driven" },
] as const;

export const PersonaDropdown = ({ persona, setPersona, customPersonas, onAddPersona, onDeletePersona }: PersonaDropdownProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [personaName, setPersonaName] = useState("");
    const [personaInstructions, setPersonaInstructions] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const nameInputRef = useRef<HTMLInputElement>(null);
    const [dropdownPos, setDropdownPos] = useState({ bottom: 0, left: 0 });

    const updatePos = useCallback(() => {
        if (triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setDropdownPos({ bottom: window.innerHeight - rect.top + 8, left: rect.left });
        }
    }, []);

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

    // Close on outside click
    useEffect(() => {
        if (!isOpen) return;
        const handleClickOutside = (e: MouseEvent) => {
            const target = e.target as Node;
            if (
                triggerRef.current && !triggerRef.current.contains(target) &&
                dropdownRef.current && !dropdownRef.current.contains(target)
            ) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [isOpen]);

    // Focus name input when modal opens
    useEffect(() => {
        if (isModalOpen) {
            setTimeout(() => nameInputRef.current?.focus(), 100);
        }
    }, [isModalOpen]);

    // Find the current persona label
    const builtIn = BUILT_IN_PERSONAS.find(p => p.id === persona);
    const custom = customPersonas.find(p => `custom-${p.persona_id}` === persona);
    const currentLabel = builtIn?.label || custom?.name || "Default";
    const CurrentIcon = builtIn?.icon || Sparkles;
    const isCustomActive = persona !== "default";

    const handleSavePersona = async () => {
        if (!personaName.trim() || !personaInstructions.trim()) return;
        setIsSaving(true);
        try {
            await onAddPersona(personaName.trim(), personaInstructions.trim());
            setPersonaName("");
            setPersonaInstructions("");
            setIsModalOpen(false);
        } catch (err) {
            console.error("Failed to save persona:", err);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeletePersona = async (e: React.MouseEvent, personaId: string) => {
        e.stopPropagation();
        try {
            // If the deleted persona is currently active, switch to default
            if (persona === `custom-${personaId}`) {
                setPersona("default");
            }
            await onDeletePersona(personaId);
        } catch (err) {
            console.error("Failed to delete persona:", err);
        }
    };

    const dropdown = isOpen && createPortal(
        <div
            ref={dropdownRef}
            className="fixed z-[200] w-[260px] rounded-xl bg-[#1e1e1e] border border-white/10 shadow-2xl shadow-black/70 animate-slide-up"
            style={{
                bottom: dropdownPos.bottom,
                left: dropdownPos.left,
            }}
        >
            <div className="p-1.5 max-h-[340px] overflow-y-auto scrollbar-hide">
                {/* Built-in personas */}
                {BUILT_IN_PERSONAS.map((p) => {
                    const Icon = p.icon;
                    const active = persona === p.id;
                    return (
                        <button
                            key={p.id}
                            onClick={() => {
                                setPersona(p.id);
                                setIsOpen(false);
                            }}
                            className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                        >
                            <div className="flex items-center gap-2.5">
                                <Icon size={15} className={cn(
                                    active ? "text-amber-400" : "text-neutral-400"
                                )} />
                                <div className="text-left">
                                    <div className="font-medium text-xs">{p.label}</div>
                                    <div className="text-[10px] text-neutral-500">{p.description}</div>
                                </div>
                            </div>
                            {active && <Check size={14} className="text-amber-400 shrink-0" />}
                        </button>
                    );
                })}

                {/* Custom personas section */}
                {customPersonas.length > 0 && (
                    <>
                        <div className="mx-3 my-1 h-px bg-white/5" />
                        <div className="px-3 py-1.5">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">Custom</span>
                        </div>
                        {customPersonas.map((cp) => {
                            const isActive = persona === `custom-${cp.persona_id}`;
                            return (
                                <button
                                    key={cp.persona_id}
                                    onClick={() => {
                                        setPersona(`custom-${cp.persona_id}`);
                                        setIsOpen(false);
                                    }}
                                    className="group w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        <Sparkles size={15} className={cn(
                                            isActive ? "text-violet-400" : "text-neutral-400"
                                        )} />
                                        <div className="text-left min-w-0">
                                            <div className="font-medium text-xs truncate">{cp.name}</div>
                                            <div className="text-[10px] text-neutral-500 truncate max-w-[140px]">{cp.instructions}</div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                        {isActive && <Check size={14} className="text-violet-400" />}
                                        <button
                                            onClick={(e) => handleDeletePersona(e, cp.persona_id)}
                                            className="flex h-5 w-5 items-center justify-center rounded text-neutral-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                                        >
                                            <Trash2 size={11} />
                                        </button>
                                    </div>
                                </button>
                            );
                        })}
                    </>
                )}

                {/* + Add a Persona */}
                <div className="mx-3 my-1 h-px bg-white/5" />
                <button
                    onClick={() => {
                        setIsOpen(false);
                        setIsModalOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                >
                    <Plus size={15} className="text-neutral-400" />
                    <span className="font-medium text-xs">Add a Persona</span>
                </button>
            </div>
        </div>,
        document.body
    );

    // ── Add Persona Modal ──
    const modal = isModalOpen && createPortal(
        <div
            className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
            onClick={() => setIsModalOpen(false)}
        >
            <div
                className="relative w-full max-w-md mx-4 rounded-2xl bg-[#1e1e1e] border border-white/10 shadow-2xl shadow-black/80 overflow-hidden animate-scaled-in"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
                    <div className="flex items-center gap-2">
                        <Sparkles size={16} className="text-violet-400" />
                        <h3 className="text-sm font-bold text-white">Create Custom Persona</h3>
                    </div>
                    <button
                        onClick={() => setIsModalOpen(false)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:text-white hover:bg-white/5 transition-all"
                    >
                        <X size={16} />
                    </button>
                </div>

                {/* Form */}
                <div className="p-5 space-y-4">
                    {/* Name */}
                    <div>
                        <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
                            Persona Name
                        </label>
                        <input
                            ref={nameInputRef}
                            type="text"
                            value={personaName}
                            onChange={(e) => setPersonaName(e.target.value)}
                            placeholder="e.g., Scientific Reviewer, Technical Writer..."
                            className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500/40 transition-all"
                            maxLength={100}
                        />
                    </div>

                    {/* Instructions */}
                    <div>
                        <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">
                            Instructions
                        </label>
                        <textarea
                            value={personaInstructions}
                            onChange={(e) => setPersonaInstructions(e.target.value)}
                            placeholder="Describe how this persona should behave, write, and approach research..."
                            rows={4}
                            className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500/40 transition-all resize-none"
                        />
                    </div>
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-2 px-5 pb-5">
                    <button
                        onClick={() => setIsModalOpen(false)}
                        className="px-4 py-2 rounded-xl text-sm text-neutral-400 hover:text-white hover:bg-white/5 transition-all"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSavePersona}
                        disabled={!personaName.trim() || !personaInstructions.trim() || isSaving}
                        className={cn(
                            "px-5 py-2 rounded-xl text-sm font-semibold transition-all",
                            personaName.trim() && personaInstructions.trim() && !isSaving
                                ? "bg-violet-500/20 border border-violet-500/30 text-violet-300 hover:bg-violet-500/30 active:scale-95"
                                : "bg-white/5 text-neutral-600 cursor-not-allowed"
                        )}
                    >
                        {isSaving ? "Saving..." : "Create Persona"}
                    </button>
                </div>
            </div>
        </div>,
        document.body
    );

    return (
        <>
            <button
                ref={triggerRef}
                onClick={() => setIsOpen(!isOpen)}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap select-none",
                    isCustomActive
                        ? persona.startsWith("custom-")
                            ? "bg-violet-500/10 border-violet-500/30 text-violet-400"
                            : "bg-amber-500/10 border-amber-500/30 text-amber-400"
                        : "bg-white/5 border-white/5 text-neutral-500 hover:bg-white/10 hover:text-white"
                )}
            >
                <CurrentIcon size={12} />
                <span>{currentLabel}</span>
                <ChevronDown size={10} className={cn("transition-transform", isOpen && "rotate-180")} />
            </button>
            {dropdown}
            {modal}
        </>
    );
};
