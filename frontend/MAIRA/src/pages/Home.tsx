import { Link } from 'react-router-dom';
import { Shield, ArrowRight, Sparkles, Globe, FileText, Brain, Zap, CheckCircle, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Home = () => {
    const { user, signOut } = useAuth();

    return (
        <div className="min-h-screen bg-[#080808] relative overflow-x-hidden">
            {/* Background Effects */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-[800px] bg-violet-600/10 blur-[200px] pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-blue-600/5 blur-[150px] pointer-events-none" />
            <div className="absolute top-1/2 left-0 w-[400px] h-[400px] bg-indigo-600/5 blur-[120px] pointer-events-none" />
            
            {/* Navigation */}
            <nav className="relative z-20 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
                <Link to="/" className="flex items-center gap-3 group">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-500/20">
                        <Shield className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-xl font-black text-white tracking-tight">MAIRA</span>
                </Link>
                
                <div className="flex items-center gap-4">
                    {user ? (
                        <>
                            <Link
                                to="/chat"
                                className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-violet-600 text-white font-bold text-sm hover:bg-violet-500 transition-all shadow-lg shadow-violet-600/20"
                            >
                                Go to Chat
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                            <button
                                onClick={() => signOut()}
                                aria-label="Sign out"
                                title="Sign out"
                                className="flex items-center gap-2 px-5 py-2.5 rounded-full border border-violet-500/20 text-violet-300 font-bold text-sm hover:bg-violet-500/10 transition-all"
                            >
                                <LogOut className="h-4 w-4" />
                            </button>
                        </>
                    ) : (
                        <>
                            <Link
                                to="/login"
                                className="px-5 py-2.5 rounded-full text-neutral-300 font-medium text-sm hover:text-white transition-all"
                            >
                                Sign In
                            </Link>
                            <Link
                                to="/signup"
                                className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-violet-600 text-white font-bold text-sm hover:bg-violet-500 transition-all shadow-lg shadow-violet-600/20"
                            >
                                Get Started
                                <ArrowRight className="h-4 w-4" />
                            </Link>
                        </>
                    )}
                </div>
            </nav>

            {/* Hero Section */}
            <main className="relative z-10 max-w-7xl mx-auto px-8 pt-20 pb-32">
                <div className="text-center max-w-4xl mx-auto">
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-bold uppercase tracking-wider mb-8">
                        <Sparkles className="h-3.5 w-3.5" />
                        AI-Powered Research Agent
                    </div>
                    
                    {/* Heading */}
                    <h1 className="text-5xl md:text-7xl font-black text-white tracking-tight leading-[1.1] mb-6">
                        Research smarter with{' '}
                        <span className="bg-gradient-to-r from-violet-400 via-indigo-400 to-blue-400 bg-clip-text text-transparent">
                            MAIRA
                        </span>
                    </h1>
                    
                    {/* Subtitle */}
                    <p className="text-lg md:text-xl text-neutral-400 leading-relaxed max-w-2xl mx-auto mb-10">
                        Your advanced AI research assistant that browses the web, analyzes papers, 
                        and generates comprehensive reports with verified sources.
                    </p>
                    
                    {/* CTA Button */}
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link
                            to={user ? "/chat" : "/signup"}
                            className="group flex items-center gap-3 px-8 py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-lg hover:shadow-2xl hover:shadow-violet-500/30 transition-all hover:scale-105"
                        >
                            <Shield className="h-5 w-5" />
                            Chat with MAIRA
                            <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                        </Link>
                        
                        {!user && (
                            <Link
                                to="/login"
                                className="px-8 py-4 rounded-2xl border border-white/10 text-white font-medium text-lg hover:bg-white/5 transition-all"
                            >
                                I have an account
                            </Link>
                        )}
                    </div>
                </div>

                {/* Features Grid */}
                <div className="mt-32 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[
                        {
                            icon: Globe,
                            title: 'Deep Research',
                            description: 'Conducts extensive autonomous research across the web to gather comprehensive data on any topic.',
                            bgClass: 'bg-blue-500/10',
                            textClass: 'text-blue-400',
                        },
                        {
                            icon: FileText,
                            title: 'Literature Surveys',
                            description: 'Generates detailed literature surveys by analyzing and synthesizing academic papers and journals.',
                            bgClass: 'bg-emerald-500/10',
                            textClass: 'text-emerald-400',
                        },
                        {
                            icon: Brain,
                            title: 'Deep Reasoning',
                            description: 'Advanced reasoning capabilities to connect complex ideas and generate novel insights.',
                            bgClass: 'bg-violet-500/10',
                            textClass: 'text-violet-400',
                        },
                        {
                            icon: CheckCircle,
                            title: 'Source Verification',
                            description: 'Every claim is rigorously verified and linked back to credible, primary sources.',
                            bgClass: 'bg-amber-500/10',
                            textClass: 'text-amber-400',
                        },
                        {
                            icon: Zap,
                            title: 'Comprehensive Reports',
                            description: 'Produces professional-grade reports in PDF and DOCX formats suitable for academic use.',
                            bgClass: 'bg-rose-500/10',
                            textClass: 'text-rose-400',
                        },
                        {
                            icon: Sparkles,
                            title: 'Multi-Model AI',
                            description: 'Powered by Claude, Gemini, and other leading AI models for superior accuracy.',
                            bgClass: 'bg-indigo-500/10',
                            textClass: 'text-indigo-400',
                        },
                    ].map((feature) => (
                        <div
                            key={feature.title}
                            className="group p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/5 hover:border-white/10 transition-all"
                        >
                            <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${feature.bgClass} mb-4`}>
                                <feature.icon className={`h-6 w-6 ${feature.textClass}`} />
                            </div>
                            <h3 className="text-lg font-bold text-white mb-2">{feature.title}</h3>
                            <p className="text-sm text-neutral-400 leading-relaxed">{feature.description}</p>
                        </div>
                    ))}
                </div>

                {/* How it Works */}
                <div className="mt-32 text-center">
                    <h2 className="text-3xl md:text-4xl font-black text-white mb-4">How it works</h2>
                    <p className="text-neutral-400 mb-16 max-w-xl mx-auto">
                        Get from question to comprehensive research report in three simple steps.
                    </p>
                    
                    <div className="flex flex-col md:flex-row items-center justify-center gap-8">
                        {[
                            { step: '01', title: 'Ask a Question', desc: 'Type your research question or topic' },
                            { step: '02', title: 'AI Researches', desc: 'MAIRA searches, analyzes, and synthesizes' },
                            { step: '03', title: 'Get Results', desc: 'Receive a verified, comprehensive report' },
                        ].map((item, idx) => (
                            <div key={item.step} className="flex items-center gap-6">
                                <div className="text-center">
                                    <div className="text-5xl font-black text-violet-500/20 mb-2">{item.step}</div>
                                    <h3 className="text-lg font-bold text-white mb-1">{item.title}</h3>
                                    <p className="text-sm text-neutral-500">{item.desc}</p>
                                </div>
                                {idx < 2 && (
                                    <ArrowRight className="hidden md:block h-6 w-6 text-neutral-700" />
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </main>

            {/* Footer */}
            <footer className="relative z-10 border-t border-white/5 py-8">
                <div className="max-w-7xl mx-auto px-8 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600/20">
                            <Shield className="h-4 w-4 text-violet-400" />
                        </div>
                        <span className="text-sm font-bold text-neutral-400">MAIRA</span>
                    </div>
                    <p className="text-xs text-neutral-600">
                        © 2026 MAIRA Research Agent. Built with advanced AI technology.
                    </p>
                </div>
            </footer>
        </div>
    );
};
