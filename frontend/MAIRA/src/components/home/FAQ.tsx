
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Minus } from 'lucide-react';

const faqs = [
    {
        question: "What is MAIRA?",
        answer: "MAIRA is an AI-powered research workspace. It autonomously browses the web, reads academic papers, and synthesizes information into comprehensive reports, saving you hours of manual work."
    },
    {
        question: "How accurate is the research?",
        answer: "Unlike standard chatbots, MAIRA verifies every claim against primary sources. It provides citations for all information, ensuring high reliability for academic and professional use."
    },
    {
        question: "Can I export my reports?",
        answer: "Yes! You can export your research as fully formatted PDF or DOCX files, ready for sharing or further editing in your favorite word processor."
    },
    {
        question: "What AI models does it use?",
        answer: "MAIRA leverages a multi-model approach, utilizing the best-in-class models like Claude 3.5 Sonnet, GPT-4o, and Gemini 1.5 Pro to ensure nuanced understanding and high-quality writing."
    }
];

export const FAQ = () => {
    const [openIndex, setOpenIndex] = useState<number | null>(null);

    return (
        <section className="py-24 max-w-4xl mx-auto px-6 scroll-mt-32" id="faq">
            <div className="text-center mb-16">
                <h2 className="text-3xl md:text-5xl font-black text-black dark:text-white mb-6">
                    Frequently Asked Questions
                </h2>
                <p className="text-black dark:text-neutral-400">
                    Everything you need to know about the product and billing.
                </p>
            </div>

            <div className="space-y-4">
                {faqs.map((faq, idx) => (
                    <div
                        key={idx}
                        className="border border-neutral-200 dark:border-white/10 rounded-2xl bg-white dark:bg-white/[0.02] overflow-hidden"
                    >
                        <button
                            onClick={() => setOpenIndex(openIndex === idx ? null : idx)}
                            className="w-full flex items-center justify-between p-6 text-left hover:bg-neutral-50 dark:hover:bg-white/5 transition-colors"
                        >
                            <span className="text-lg font-bold text-black dark:text-white pr-8">
                                {faq.question}
                            </span>
                            <span className="flex-shrink-0 text-violet-400">
                                {openIndex === idx ? <Minus className="w-5 h-5" /> : <Plus className="w-5 h-5" />}
                            </span>
                        </button>
                        <AnimatePresence>
                            {openIndex === idx && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    <div className="p-6 pt-0 text-black dark:text-neutral-400 leading-relaxed border-t border-neutral-100 dark:border-white/5 mt-2">
                                        {faq.answer}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                ))}
            </div>
        </section>
    );
};
