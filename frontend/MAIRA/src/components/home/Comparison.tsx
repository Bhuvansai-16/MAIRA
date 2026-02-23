
import { motion } from 'framer-motion';
import { XCircle, CheckCircle2, ShieldAlert, Zap, Globe, Brain, FileOutput, Sparkles } from 'lucide-react';

export const Comparison = () => {
    const negatives = [
        "Hallucinates facts & makes up sources",
        "Loses context in complex research",
        "No real citations or verifiable data",
        "Forces manual copy-pasting to Word",
        "Generic output with no personalization"
    ];

    const positives = [
        { text: "Autonomous web & arXiv scraping", icon: Globe },
        { text: "Fact-checking (Deep Reasoning)", icon: Brain },
        { text: "Verifiable citations for every claim", icon: CheckCircle2 },
        { text: "Instant PDF/DOCX/LaTeX export", icon: FileOutput },
        { text: "Custom Personas for tailored research", icon: Sparkles }
    ];

    return (
        <div className="relative w-full max-w-6xl mx-auto mt-20 px-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-0 md:gap-8 relative">
                {/* Standard AI Card */}
                <motion.div
                    initial={{ opacity: 0, x: -30 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="relative overflow-hidden rounded-[40px] border border-neutral-200 dark:border-white/5 bg-white/50 dark:bg-neutral-900/20 backdrop-blur-md p-8 md:p-12"
                >
                    <div className="flex items-center gap-4 mb-10">
                        <div className="p-3 rounded-2xl bg-red-500/10 text-red-500">
                            <ShieldAlert className="w-8 h-8" />
                        </div>
                        <div>
                            <h3 className="text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-400">Standard LLMs</h3>
                            <p className="text-sm text-red-500/80 font-medium">The "Generic" Experience</p>
                        </div>
                    </div>

                    <ul className="space-y-6">
                        {negatives.map((item, i) => (
                            <li key={i} className="flex items-start gap-4 text-neutral-600 dark:text-neutral-500 text-base md:text-lg">
                                <XCircle className="w-6 h-6 text-red-500/60 shrink-0 mt-0.5" />
                                <span>{item}</span>
                            </li>
                        ))}
                    </ul>
                </motion.div>

                {/* MAIRA Card */}
                <motion.div
                    initial={{ opacity: 0, x: 30 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
                    className="relative z-10 overflow-hidden rounded-[40px] border border-violet-500/30 bg-white dark:bg-black p-8 md:p-12 shadow-[0_0_80px_-20px_rgba(139,92,246,0.3)] mt-[-20px] md:mt-0"
                >
                    {/* Glowing Accents */}
                    <div className="absolute -top-24 -right-24 w-64 h-64 bg-violet-600/20 blur-[100px] pointer-events-none" />
                    <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-indigo-600/10 blur-[120px] pointer-events-none" />

                    <div className="flex items-center gap-4 mb-10">
                        <div className="p-3 rounded-2xl bg-violet-500 text-white shadow-xl shadow-violet-500/40">
                            <Zap className="w-8 h-8" />
                        </div>
                        <div>
                            <h3 className="text-2xl md:text-3xl font-black text-neutral-900 dark:text-white">MAIRA</h3>
                            <p className="text-sm text-violet-500 font-bold uppercase tracking-widest">Purpose-Built for Research</p>
                        </div>
                    </div>

                    <ul className="space-y-6">
                        {positives.map((item, i) => (
                            <li key={i} className="flex items-start gap-4 text-neutral-900 dark:text-neutral-200 font-semibold text-base md:text-lg">
                                <CheckCircle2 className="w-6 h-6 text-emerald-500 shrink-0 mt-0.5" />
                                <span>{item.text}</span>
                            </li>
                        ))}
                    </ul>

                </motion.div>
            </div>
        </div>
    );
};
