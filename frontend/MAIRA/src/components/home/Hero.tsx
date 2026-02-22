
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, Wand2, PenTool } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Comparison } from './Comparison';

export const Hero = () => {
    const { user } = useAuth();

    return (
        <section className="relative pt-48 pb-20 md:pt-64 md:pb-32 overflow-hidden">
            {/* Background Effects */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-r from-violet-600/20 via-blue-500/20 to-cyan-400/20 blur-[100px] opacity-40 rounded-full mix-blend-screen" />
                <div className="absolute bottom-0 right-0 w-[800px] h-[800px] bg-indigo-500/10 blur-[120px] rounded-full opacity-30" />
            </div>

            <div className="container relative z-10 px-6 mx-auto text-center">

                <motion.h1
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
                    className="text-5xl md:text-7xl lg:text-8xl font-black text-neutral-900 dark:text-white tracking-tight leading-[1.1] mb-8"
                >
                    Replace your entire <br />
                    <span className="text-black dark:text-transparent dark:bg-clip-text dark:bg-gradient-to-r dark:from-violet-400 dark:via-fuchsia-400 dark:to-indigo-400">
                        research stack
                    </span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
                    className="max-w-2xl mx-auto text-lg md:text-xl text-black dark:text-neutral-400/80 mb-12 leading-relaxed"
                >
                    Research, draft, and synthesize without leaving your flow.
                    Smater, faster, and cleaner than traditional tools combined.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.3, ease: "easeOut" }}
                    className="flex flex-col sm:flex-row items-center justify-center gap-4"
                >
                    <Link
                        to={user ? "/chat" : "/signup"}
                        className={`group relative inline-flex items-center justify-center gap-3 px-8 py-4 text-lg font-bold text-black transition-all bg-white rounded-full ${user ? 'cursor-default' : 'hover:bg-neutral-100 hover:scale-105 active:scale-95 shadow-[0_0_40px_-10px_rgba(255,255,255,0.3)]'}`}
                    >
                        <Wand2 className="w-5 h-5 transition-transform group-hover:rotate-12" />
                        <span>Start Researching</span>
                        <ArrowRight className="w-5 h-5 transition-transform group-hover:translate-x-1" />
                    </Link>

                    <Link
                        to={user ? "/paper-writer" : "/signup"}
                        className="group relative inline-flex items-center justify-center gap-3 px-8 py-4 text-lg font-bold text-black dark:text-white transition-all bg-neutral-100 dark:bg-white/5 border border-black dark:border-white/10 rounded-full hover:bg-neutral-200 dark:hover:bg-white/10 hover:border-black dark:hover:border-white/20 hover:scale-105 active:scale-95 backdrop-blur-sm"
                    >
                        <PenTool className="w-5 h-5" />
                        <span>Write Paper</span>
                    </Link>
                </motion.div>

                {!user && (
                    <div className="flex items-center justify-center gap-2 text-sm text-neutral-500 mt-8">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span>No credit card required</span>
                    </div>
                )}

                {/* Comparison Section (Replaces abstract UI) */}
                <Comparison />
            </div>
        </section>
    );
};
