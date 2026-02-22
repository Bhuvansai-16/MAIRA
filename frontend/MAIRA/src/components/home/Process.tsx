
import { motion } from 'framer-motion';
import { Search, BrainCircuit, FileOutput } from 'lucide-react';

const steps = [
    {
        step: '01',
        title: 'Ask a Question',
        desc: 'Enter your research topic or question. MAIRA understands complex queries and intent.',
        icon: Search
    },
    {
        step: '02',
        title: 'Deep Research',
        desc: 'MAIRA autonomously browses the web, reads papers, and verifies facts across multiple sources.',
        icon: BrainCircuit
    },
    {
        step: '03',
        title: 'Receive Report',
        desc: 'Get a comprehensive, cited report in PDF or DOCX format, ready for use.',
        icon: FileOutput
    }
];

export const Process = () => {
    return (
        <section className="py-24 bg-neutral-50 dark:bg-neutral-900/20 scroll-mt-32" id="how-it-works">
            <div className="max-w-7xl mx-auto px-6">
                <div className="text-center mb-20">
                    <h2 className="text-3xl md:text-5xl font-black text-black dark:text-white mb-6">
                        From Question to Insight
                    </h2>
                    <p className="text-black dark:text-neutral-400 max-w-xl mx-auto text-lg">
                        Three simple steps to automate hours of manual research work.
                    </p>
                </div>

                <div className="relative grid grid-cols-1 md:grid-cols-3 gap-12">
                    {/* Connector Line (Desktop) */}
                    <div className="hidden md:block absolute top-12 left-0 right-0 h-0.5 bg-gradient-to-r from-violet-500/0 via-violet-500/20 to-violet-500/0" />

                    {steps.map((item, idx) => {
                        const Icon = item.icon;
                        return (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, y: 30 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: idx * 0.2 }}
                                className="relative z-10 group"
                            >
                                {/* Step Number Circle */}
                                <div className="w-24 h-24 mx-auto bg-white dark:bg-black border border-neutral-200 dark:border-white/10 rounded-full flex items-center justify-center mb-8 shadow-[0_0_30px_-10px_rgba(139,92,246,0.1)] group-hover:shadow-[0_0_30px_-5px_rgba(139,92,246,0.3)] transition-all duration-500">
                                    <Icon className="w-10 h-10 text-violet-400 group-hover:scale-110 transition-transform duration-300" />
                                </div>

                                <div className="text-center">
                                    <div className="text-sm font-bold text-violet-500 mb-2 tracking-widest uppercase">Step {item.step}</div>
                                    <h3 className="text-2xl font-bold text-black dark:text-white mb-4">{item.title}</h3>
                                    <p className="text-black dark:text-neutral-400 leading-relaxed px-4">
                                        {item.desc}
                                    </p>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};
