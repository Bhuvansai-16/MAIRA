import { useState } from "react";
import { createPortal } from "react-dom";
import {
    X, Globe, User, Check,
    Plus, Trash2, Sparkles, GraduationCap, Microscope,
} from "lucide-react";
import { cn } from "../lib/utils";
import type { CustomPersona } from "./PersonaDropdown";

// ─────────────────────────────────────────────
//  Types
// ─────────────────────────────────────────────
type SettingsTab = "sites" | "persona";

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    // Sites
    sites: string[];
    setSites: (sites: string[]) => void;
    isSiteRestrictionEnabled: boolean;
    setIsSiteRestrictionEnabled: (enabled: boolean) => void;
    // Persona
    persona: string;
    setPersona: (persona: string) => void;
    customPersonas: CustomPersona[];
    onAddPersona: (name: string, instructions: string) => Promise<void>;
    onUpdatePersona: (personaId: string, name: string, instructions: string) => Promise<void>;
    onDeletePersona: (personaId: string) => Promise<void>;
}

const BUILT_IN_PERSONAS = [
    { id: "default", label: "Default", icon: User, description: "Balanced research assistant" },
    { id: "student", label: "Student", icon: User, description: "Simple, clear explanations" },
    { id: "professor", label: "Professor", icon: GraduationCap, description: "Academic & authoritative" },
    { id: "researcher", label: "Researcher", icon: Microscope, description: "Technical & data-driven" },
] as const;

const TABS: { id: SettingsTab; label: string; icon: React.FC<{ size?: number; className?: string }> }[] = [
    { id: "sites", label: "Sites", icon: Globe },
    { id: "persona", label: "Persona", icon: User },
];

// ─────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────
const cleanUrl = (url: string) => {
    let c = url.trim().toLowerCase();
    c = c.replace(/^https?:\/\//, "");
    c = c.replace(/\/$/, "");
    c = c.replace(/^www\./, "");
    return c;
};

const countWords = (str: string) => {
    return str.trim().split(/\s+/).filter(Boolean).length;
};

// ─────────────────────────────────────────────
//  Main Component
// ─────────────────────────────────────────────
export const SettingsModal = ({
    isOpen,
    onClose,
    sites,
    setSites,
    isSiteRestrictionEnabled,
    setIsSiteRestrictionEnabled,
    persona,
    setPersona,
    customPersonas,
    onAddPersona,
    onUpdatePersona,
    onDeletePersona,
}: SettingsModalProps) => {
    const [activeTab, setActiveTab] = useState<SettingsTab>("sites");

    // Sites state
    const [siteInput, setSiteInput] = useState("");

    // Persona state
    const [showAddPersona, setShowAddPersona] = useState(false);
    const [personaName, setPersonaName] = useState("");
    const [personaInstructions, setPersonaInstructions] = useState("");
    const [isSaving, setIsSaving] = useState(false);

    // Edit state
    const [editingPersonaId, setEditingPersonaId] = useState<string | null>(null);
    const [editInstructions, setEditInstructions] = useState("");
    const [isUpdating, setIsUpdating] = useState(false);

    if (!isOpen) return null;

    // ── Sites handlers ──
    const addSites = () => {
        if (!siteInput.trim()) return;
        const newSites = siteInput
            .split(",")
            .map(cleanUrl)
            .filter((s) => s.length > 0 && !sites.includes(s));
        if (newSites.length > 0) {
            setSites([...sites, ...newSites]);
            setIsSiteRestrictionEnabled(true);
        }
        setSiteInput("");
    };

    const removeSite = (site: string) => setSites(sites.filter((s) => s !== site));

    // ── Persona handlers ──
    const handleSavePersona = async () => {
        if (!personaName.trim() || !personaInstructions.trim()) return;
        if (countWords(personaInstructions) > 250) return;
        setIsSaving(true);
        try {
            await onAddPersona(personaName.trim(), personaInstructions.trim());
            setPersonaName("");
            setPersonaInstructions("");
            setShowAddPersona(false);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeletePersona = async (personaId: string) => {
        if (persona === `custom-${personaId}`) setPersona("default");
        await onDeletePersona(personaId);
    };

    const handleUpdatePersona = async (cp: CustomPersona) => {
        const words = countWords(editInstructions);
        if (words > 250) return;

        setIsUpdating(true);
        try {
            await onUpdatePersona(cp.persona_id, cp.name, editInstructions.trim());
            setEditingPersonaId(null);
        } finally {
            setIsUpdating(false);
        }
    };

    // ─────────────────────────────────────────
    //  Panel renderers
    // ─────────────────────────────────────────


    const renderSites = () => (
        <div className="p-6 space-y-5">
            <div>
                <h3 className="text-sm font-bold text-white mb-1">Search Site Restrictions</h3>
                <p className="text-xs text-neutral-500 mb-4">
                    Restrict web searches to these specific domains when "Search the web" is enabled.
                </p>
            </div>

            {/* Add site input */}
            <div className="flex gap-2">
                <input
                    type="text"
                    value={siteInput}
                    onChange={(e) => setSiteInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addSites(); } }}
                    placeholder="e.g. arxiv.org, nature.com"
                    className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-cyan-500/40 transition-all"
                />
                <button
                    onClick={addSites}
                    disabled={!siteInput.trim()}
                    className={cn(
                        "px-4 py-2.5 rounded-xl text-sm font-semibold transition-all",
                        siteInput.trim()
                            ? "bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/25 active:scale-95"
                            : "bg-white/5 text-neutral-600 cursor-not-allowed"
                    )}
                >
                    Add
                </button>
            </div>

            {/* Sites list */}
            {sites.length > 0 ? (
                <div className="space-y-1.5 max-h-[200px] overflow-y-auto pr-1 scrollbar-hide">
                    {sites.map((site) => (
                        <div
                            key={site}
                            className="group flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5 hover:border-white/10 transition-all"
                        >
                            <div className="flex items-center gap-2.5">
                                <Globe size={12} className="text-neutral-500 shrink-0" />
                                <span className="text-sm text-neutral-300">{site}</span>
                            </div>
                            <button
                                onClick={() => removeSite(site)}
                                className="flex h-6 w-6 items-center justify-center rounded-lg text-neutral-600 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                            >
                                <Trash2 size={12} />
                            </button>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-neutral-600 text-center py-4">No sites added yet.</p>
            )}
        </div>
    );

    const renderPersona = () => (
        <div className="p-6 space-y-4">
            <div>
                <h3 className="text-sm font-bold text-white mb-1">Research Persona</h3>
                <p className="text-xs text-neutral-500 mb-4">
                    Pick how MAIRA writes and presents research for you.
                </p>
            </div>

            {/* Built-in personas */}
            <div className="space-y-1.5">
                {BUILT_IN_PERSONAS.map((p) => {
                    const Icon = p.icon;
                    const active = persona === p.id;
                    return (
                        <button
                            key={p.id}
                            onClick={() => setPersona(p.id)}
                            className={cn(
                                "w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all",
                                active
                                    ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                                    : "border-white/5 bg-white/[0.03] text-neutral-400 hover:border-white/10 hover:bg-white/5 hover:text-white"
                            )}
                        >
                            <div className="flex items-center gap-3">
                                <Icon size={15} className={active ? "text-amber-400" : "text-neutral-500"} />
                                <div className="text-left">
                                    <div className="text-xs font-semibold">{p.label}</div>
                                    <div className="text-[10px] text-neutral-500">{p.description}</div>
                                </div>
                            </div>
                            {active && <Check size={14} className="text-amber-400 shrink-0" />}
                        </button>
                    );
                })}
            </div>

            {/* Custom personas */}
            {customPersonas.length > 0 && (
                <div className="space-y-1.5">
                    <div className="px-1 pt-1">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-600">Custom</span>
                    </div>
                    {customPersonas.map((cp) => {
                        const isActive = persona === `custom-${cp.persona_id}`;
                        const isEditing = editingPersonaId === cp.persona_id;
                        const wordCount = isEditing ? countWords(editInstructions) : 0;
                        const isOverLimit = wordCount > 250;

                        return (
                            <div
                                key={cp.persona_id}
                                className={cn(
                                    "group flex flex-col px-4 py-3 rounded-xl border transition-all cursor-pointer",
                                    isActive
                                        ? "border-violet-500/30 bg-violet-500/10"
                                        : "border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/5"
                                )}
                                onClick={() => {
                                    setPersona(`custom-${cp.persona_id}`);
                                    if (!isEditing) {
                                        setEditingPersonaId(cp.persona_id);
                                        setEditInstructions(cp.instructions);
                                    }
                                }}
                            >
                                <div className="flex items-center justify-between w-full">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Sparkles size={14} className={isActive ? "text-violet-400" : "text-neutral-500"} />
                                        <div className="min-w-0">
                                            <div className={cn("text-xs font-semibold truncate", isActive ? "text-violet-300" : "text-neutral-300")}>{cp.name}</div>
                                            {!isEditing && (
                                                <div className="text-[10px] text-neutral-500 truncate max-w-[180px]">{cp.instructions}</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-1.5 shrink-0">
                                        {isActive && !isEditing && <Check size={13} className="text-violet-400" />}
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDeletePersona(cp.persona_id); }}
                                            className="flex h-6 w-6 items-center justify-center rounded-lg text-neutral-600 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                        >
                                            <Trash2 size={11} />
                                        </button>
                                    </div>
                                </div>

                                {isEditing && (
                                    <div className="mt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
                                        <textarea
                                            autoFocus
                                            value={editInstructions}
                                            onChange={(e) => setEditInstructions(e.target.value)}
                                            className={cn(
                                                "w-full px-3 py-2 rounded-xl bg-black/20 border text-xs text-white placeholder-neutral-600 focus:outline-none transition-all resize-none",
                                                isOverLimit ? "border-red-500/50 focus:border-red-500" : "border-white/10 focus:border-violet-500/40"
                                            )}
                                            rows={3}
                                            placeholder="Edit instructions..."
                                        />
                                        <div className="flex items-center justify-between">
                                            <span className={cn(
                                                "text-[10px] font-medium",
                                                isOverLimit ? "text-red-400" : "text-neutral-500"
                                            )}>
                                                {wordCount} / 250 words
                                            </span>
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => setEditingPersonaId(null)}
                                                    className="px-2 py-1 rounded-lg text-[10px] font-semibold text-neutral-500 hover:text-white transition-all"
                                                >
                                                    Cancel
                                                </button>
                                                <button
                                                    onClick={() => handleUpdatePersona(cp)}
                                                    disabled={isUpdating || isOverLimit || !editInstructions.trim()}
                                                    className={cn(
                                                        "px-3 py-1 rounded-lg text-[10px] font-bold transition-all",
                                                        !isUpdating && !isOverLimit && editInstructions.trim()
                                                            ? "bg-violet-500/20 text-violet-300 hover:bg-violet-500/30"
                                                            : "bg-white/5 text-neutral-600 cursor-not-allowed"
                                                    )}
                                                >
                                                    {isUpdating ? "Saving..." : "Save"}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Add new persona */}
            {showAddPersona ? (
                <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-violet-300">New Persona</span>
                        <button onClick={() => setShowAddPersona(false)} className="text-neutral-500 hover:text-white transition-colors">
                            <X size={14} />
                        </button>
                    </div>
                    <input
                        type="text"
                        value={personaName}
                        onChange={(e) => setPersonaName(e.target.value)}
                        placeholder="Persona name (e.g., Startup CEO)"
                        className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-violet-500/40 transition-all"
                        maxLength={100}
                    />
                    <textarea
                        value={personaInstructions}
                        onChange={(e) => setPersonaInstructions(e.target.value)}
                        placeholder="How should this persona behave, write, and approach research?"
                        rows={3}
                        className={cn(
                            "w-full px-3 py-2 rounded-xl bg-white/5 border text-sm text-white placeholder-neutral-500 focus:outline-none transition-all resize-none",
                            countWords(personaInstructions) > 250 ? "border-red-500/50 focus:border-red-500" : "border-white/10 focus:border-violet-500/40"
                        )}
                    />
                    <div className="flex items-center justify-between">
                        <span className={cn(
                            "text-[10px] font-medium",
                            countWords(personaInstructions) > 250 ? "text-red-400" : "text-neutral-500"
                        )}>
                            {countWords(personaInstructions)} / 250 words
                        </span>
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setShowAddPersona(false)}
                                className="px-3 py-1.5 rounded-lg text-xs text-neutral-400 hover:text-white hover:bg-white/5 transition-all"
                            >Cancel</button>

                            <button
                                onClick={handleSavePersona}
                                disabled={!personaName.trim() || !personaInstructions.trim() || isSaving || countWords(personaInstructions) > 250}
                                className={cn(
                                    "px-4 py-1.5 rounded-lg text-xs font-semibold transition-all",
                                    personaName.trim() && personaInstructions.trim() && !isSaving && countWords(personaInstructions) <= 250
                                        ? "bg-violet-500/20 border border-violet-500/30 text-violet-300 hover:bg-violet-500/30 active:scale-95"
                                        : "bg-white/5 text-neutral-600 cursor-not-allowed"
                                )}
                            >{isSaving ? "Saving..." : "Create"}</button>
                        </div>
                    </div>
                </div>
            ) : (
                <button
                    onClick={() => setShowAddPersona(true)}
                    className="w-full flex items-center gap-2.5 px-4 py-3 rounded-xl border border-dashed border-white/10 text-sm text-neutral-500 hover:text-white hover:border-white/20 hover:bg-white/[0.03] transition-all"
                >
                    <Plus size={14} />
                    <span className="text-xs font-medium">Add Custom Persona</span>
                </button>
            )}
        </div>
    );

    // ─────────────────────────────────────────
    //  Modal shell
    // ─────────────────────────────────────────
    return createPortal(
        <div
            className="fixed inset-0 z-[400] flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={onClose}
        >
            <div
                className="relative w-full max-w-[620px] mx-4 rounded-3xl bg-[#141414] border border-white/10 shadow-2xl shadow-black/80 overflow-hidden flex"
                style={{ height: "min(560px, 90vh)" }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* ── Left sidebar nav ── */}
                <div className="w-[160px] shrink-0 bg-[#0f0f0f] border-r border-white/5 flex flex-col py-4 px-2 gap-1">
                    <div className="px-3 pt-1 pb-3">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-600">Settings</span>
                    </div>

                    {TABS.map((tab) => {
                        const Icon = tab.icon;
                        const active = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={cn(
                                    "flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left",
                                    active
                                        ? "bg-white/10 text-white"
                                        : "text-neutral-500 hover:bg-white/5 hover:text-neutral-300"
                                )}
                            >
                                <Icon size={15} className={active ? "text-blue-400" : "text-neutral-600"} />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>

                {/* ── Right content ── */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
                        <h2 className="text-sm font-bold text-white capitalize">{activeTab}</h2>
                        <button
                            onClick={onClose}
                            className="flex h-8 w-8 items-center justify-center rounded-xl text-neutral-500 hover:text-white hover:bg-white/10 transition-all"
                        >
                            <X size={16} />
                        </button>
                    </div>

                    {/* Body */}
                    <div className="flex-1 overflow-y-auto scrollbar-hide">
                        {activeTab === "sites" && renderSites()}
                        {activeTab === "persona" && renderPersona()}
                    </div>
                </div>
            </div>
        </div>,
        document.body
    );
};
