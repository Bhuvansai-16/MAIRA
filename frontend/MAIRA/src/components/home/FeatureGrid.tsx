
import { motion } from 'framer-motion';
import { Globe, FileText, CheckCircle, Sparkles, Zap, Brain, PenTool } from 'lucide-react';

const features = [
    {
        title: "Deep Research",
        description: "Conducts extensive autonomous research across the web to gather comprehensive data on any topic.",
        icon: Globe,
        className: "col-span-1 md:col-span-2 lg:col-span-2 row-span-2",
        gradient: "from-violet-500/20 to-indigo-500/20",
        textGradient: "text-violet-400"
    },
    {
        title: "Literature Surveys",
        description: "Analyze and synthesize thousands of academic papers in minutes.",
        icon: FileText,
        className: "col-span-1 md:col-span-1 lg:col-span-1",
        gradient: "from-emerald-500/20 to-teal-500/20",
        textGradient: "text-emerald-400"
    },
    {
        title: "Verified Sources",
        description: "Every claim is linked to a primary source.",
        icon: CheckCircle,
        className: "col-span-1 md:col-span-1 lg:col-span-1",
        gradient: "from-amber-500/20 to-orange-500/20",
        textGradient: "text-amber-400"
    },
    {
        title: "Multi-Model AI",
        description: "Powered by Claude, Gemini, and GPT-4o.",
        icon: Brain,
        className: "col-span-1 md:col-span-2 lg:col-span-2",
        gradient: "from-blue-500/20 to-cyan-500/20",
        textGradient: "text-blue-400"
    },
    {
        title: "Instant Reports",
        description: "Download PDFs and DOCX files ready for publication.",
        icon: Zap,
        className: "col-span-1 md:col-span-1 lg:col-span-2",
        gradient: "from-pink-500/20 to-rose-500/20",
        textGradient: "text-pink-400"
    },
    {
        title: "Smart Drafting",
        description: "Generate structured drafts with perfect tone.",
        icon: PenTool,
        className: "col-span-1 md:col-span-1 lg:col-span-2",
        gradient: "from-violet-500/20 to-purple-500/20",
        textGradient: "text-purple-400"
    }
];

export const FeatureGrid = () => {
    return (
        <section className="py-24 px-6 max-w-7xl mx-auto scroll-mt-32" id="features">
            <div className="text-center mb-16">
                <h2 className="text-3xl md:text-5xl font-black text-black dark:text-white tracking-tight mb-4">
                    Replace your research stack
                </h2>
                <p className="text-black dark:text-neutral-400 text-lg max-w-2xl mx-auto">
                    No more switching between tabs, notepads, and citation managers.
                    MAIRA handles the heavy lifting so you can focus on insights.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 auto-rows-[200px]">
                {features.map((feature, idx) => (
                    <motion.div
                        key={idx}
                        className={`
              relative group overflow-hidden rounded-3xl border border-neutral-200 dark:border-white/5 bg-white dark:bg-[#0A0A0A] p-8 
              hover:border-neutral-300 dark:hover:border-white/10 transition-all duration-300
              ${feature.className}
            `}
                        whileHover={{ y: -5 }}
                    >
                        <div className={`
              absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 
              group-hover:opacity-100 transition-opacity duration-500
            `} />

                        <div className="relative z-10 h-full flex flex-col justify-between">
                            <div>
                                <div className={`
                  inline-flex p-3 rounded-xl bg-white/5 mb-4 
                  ${feature.textGradient}
                `}>
                                    <feature.icon className="w-6 h-6" />
                                </div>
                                <h3 className="text-xl font-bold text-black dark:text-white mb-2">{feature.title}</h3>
                                <p className="text-black dark:text-neutral-400 text-sm leading-relaxed">
                                    {feature.description}
                                </p>
                            </div>

                            <div className="flex justify-end opacity-0 group-hover:opacity-100 transition-opacity transform translate-y-2 group-hover:translate-y-0">
                                <Sparkles className={`w-5 h-5 ${feature.textGradient}`} />
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </section>
    );
};
