import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Globe, ChevronDown, Check, Settings, X, Trash2, MoreHorizontal } from "lucide-react";
import { cn } from "../lib/utils";

interface SitesSelectorProps {
    sites: string[];
    setSites: (sites: string[]) => void;
    isSiteRestrictionEnabled: boolean;
    setIsSiteRestrictionEnabled: (enabled: boolean) => void;
}

export const SitesSelector = ({ sites, setSites, isSiteRestrictionEnabled, setIsSiteRestrictionEnabled }: SitesSelectorProps) => {
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [inputValue, setInputValue] = useState("");
    const triggerRef = useRef<HTMLButtonElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const modalInputRef = useRef<HTMLInputElement>(null);
    const [dropdownPos, setDropdownPos] = useState({ bottom: 0, left: 0 });

    // Calculate dropdown position from trigger button
    const updateDropdownPos = useCallback(() => {
        if (triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setDropdownPos({
                bottom: window.innerHeight - rect.top + 8, // Anchor to bottom of viewport, 8px above button
                left: rect.left,
            });
        }
    }, []);

    // Recalculate on open & scroll/resize
    useEffect(() => {
        if (!isDropdownOpen) return;
        updateDropdownPos();
        window.addEventListener("scroll", updateDropdownPos, true);
        window.addEventListener("resize", updateDropdownPos);
        return () => {
            window.removeEventListener("scroll", updateDropdownPos, true);
            window.removeEventListener("resize", updateDropdownPos);
        };
    }, [isDropdownOpen, updateDropdownPos]);

    // Close dropdown on outside click
    useEffect(() => {
        if (!isDropdownOpen) return;
        const handleClickOutside = (e: MouseEvent) => {
            const target = e.target as Node;
            if (
                triggerRef.current && !triggerRef.current.contains(target) &&
                dropdownRef.current && !dropdownRef.current.contains(target)
            ) {
                setIsDropdownOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [isDropdownOpen]);

    // Focus modal input when modal opens
    useEffect(() => {
        if (isModalOpen) {
            setTimeout(() => modalInputRef.current?.focus(), 100);
        }
    }, [isModalOpen]);

    const cleanUrl = (url: string): string => {
        let cleaned = url.trim().toLowerCase();
        cleaned = cleaned.replace(/^https?:\/\//, '');
        cleaned = cleaned.replace(/\/$/, '');
        cleaned = cleaned.replace(/^www\./, '');
        return cleaned;
    };

    const addSites = () => {
        if (!inputValue.trim()) return;
        const newSites = inputValue
            .split(',')
            .map(s => cleanUrl(s))
            .filter(s => s.length > 0 && !sites.includes(s));
        if (newSites.length > 0) {
            setSites([...sites, ...newSites]);
            setIsSiteRestrictionEnabled(true); // Enable restriction when adding sites
        }
        setInputValue("");
    };

    const removeSite = (site: string) => {
        setSites(sites.filter(s => s !== site));
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addSites();
        }
    };

    const isActive = isSiteRestrictionEnabled && sites.length > 0;

    // ── Dropdown (rendered via portal at body level) ──
    const dropdown = isDropdownOpen && createPortal(
        <div
            ref={dropdownRef}
            className="fixed z-[200] w-[260px] rounded-xl bg-[#1e1e1e] border border-white/10 shadow-2xl shadow-black/70 animate-slide-up"
            style={{
                bottom: dropdownPos.bottom,
                left: dropdownPos.left,
                // transform: "translateY(-100%)", // No longer needed with bottom positioning
            }}
        >
            <div className="p-1.5">
                {/* Search the web */}
                <button
                    onClick={() => {
                        setIsSiteRestrictionEnabled(false);
                        setIsDropdownOpen(false);
                    }}
                    className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                >
                    <div className="flex items-center gap-2.5">
                        <Globe size={16} className="text-neutral-400" />
                        <span className="font-medium">Search the web</span>
                    </div>
                    {!isSiteRestrictionEnabled && <Check size={14} className="text-white" />}
                </button>

                <div className="mx-3 my-0.5 h-px bg-white/5" />

                {/* Specific sites header */}
                <button
                    onClick={() => {
                        if (sites.length === 0) {
                            setIsDropdownOpen(false);
                            setIsModalOpen(true);
                        } else {
                            setIsSiteRestrictionEnabled(true);
                            setIsDropdownOpen(false);
                        }
                    }}
                    className="w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                >
                    <div className="flex items-center gap-2.5">
                        <Globe size={16} className="text-neutral-400" />
                        <span className="font-medium">Specific sites ({sites.length})</span>
                    </div>
                    {isSiteRestrictionEnabled && <Check size={14} className="text-white" />}
                </button>

                {/* Listed sites (shown inline in dropdown when sites exist) */}
                {sites.length > 0 && (
                    <div className={cn("px-2 pb-1 pt-0.5 flex flex-col gap-0.5", !isSiteRestrictionEnabled && "opacity-50")}>
                        {sites.map((site) => (
                            <div
                                key={site}
                                className="group flex items-center justify-between px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors"
                            >
                                <span className="text-xs text-neutral-400 truncate">{site}</span>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeSite(site);
                                    }}
                                    className="flex h-5 w-5 items-center justify-center rounded text-neutral-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all shrink-0 ml-2"
                                >
                                    <X size={11} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="mx-3 my-0.5 h-px bg-white/5" />

                {/* Manage sites */}
                <button
                    onClick={() => {
                        setIsDropdownOpen(false);
                        setIsModalOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-neutral-300 hover:bg-white/5 hover:text-white transition-colors"
                >
                    <Settings size={16} className="text-neutral-400" />
                    <span className="font-medium">Manage sites</span>
                </button>
            </div>
        </div>,
        document.body
    );

    // ── Modal (rendered via portal) ──
    const modal = isModalOpen && createPortal(
        <div
            className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
            onClick={() => setIsModalOpen(false)}
        >
            <div
                className="relative w-full max-w-md mx-4 rounded-2xl bg-[#1e1e1e] border border-white/10 shadow-2xl shadow-black/80 overflow-hidden animate-scaled-in"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header — matches reference Image 2 */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
                    <h3 className="text-sm font-bold text-white">Search specific sites</h3>
                    <div className="flex items-center gap-1">
                        <button className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:text-white hover:bg-white/5 transition-all">
                            <MoreHorizontal size={16} />
                        </button>
                        <button
                            onClick={() => setIsModalOpen(false)}
                            className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:text-white hover:bg-white/5 transition-all"
                        >
                            <X size={16} />
                        </button>
                    </div>
                </div>

                {/* Input row — matches reference Image 2 */}
                <div className="p-5 pb-3">
                    <div className="flex gap-2">
                        <input
                            ref={modalInputRef}
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Add site URLs, separated by commas"
                            className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-white/20 transition-all"
                        />
                        <button
                            onClick={addSites}
                            disabled={!inputValue.trim()}
                            className={cn(
                                "px-5 py-2.5 rounded-xl text-sm font-semibold transition-all",
                                inputValue.trim()
                                    ? "bg-white/10 text-white hover:bg-white/20 active:scale-95"
                                    : "bg-white/5 text-neutral-600 cursor-not-allowed"
                            )}
                        >
                            Add
                        </button>
                    </div>
                </div>

                {/* Sites list */}
                {sites.length > 0 && (
                    <div className="px-5 pb-4 max-h-[240px] overflow-y-auto scrollbar-hide">
                        <div className="flex flex-col gap-1">
                            {sites.map((site) => (
                                <div
                                    key={site}
                                    className="group flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5 hover:border-white/10 transition-all"
                                >
                                    <div className="flex items-center gap-2.5">
                                        <Globe size={13} className="text-neutral-500 shrink-0" />
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
                    </div>
                )}
            </div>
        </div>,
        document.body
    );

    return (
        <>
            {/* Trigger button */}
            <button
                ref={triggerRef}
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap select-none",
                    isActive
                        ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400"
                        : "bg-white/5 border-white/5 text-neutral-500 hover:bg-white/10 hover:text-white"
                )}
            >
                <Globe size={12} />
                <span>Sites{isActive ? ` (${sites.length})` : ''}</span>
                <ChevronDown size={10} className={cn("transition-transform", isDropdownOpen && "rotate-180")} />
            </button>

            {dropdown}
            {modal}
        </>
    );
};
