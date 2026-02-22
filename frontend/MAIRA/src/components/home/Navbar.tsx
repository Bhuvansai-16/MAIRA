
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Menu, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ThemeToggle } from '../ThemeToggle';

export const Navbar = () => {
    const { user, signOut } = useAuth();
    const [scrolled, setScrolled] = useState(false);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20);
        };
        // Set initial state immediately
        handleScroll();
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleScrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
        if (href.startsWith('#')) {
            e.preventDefault();
            const element = document.querySelector(href);
            if (element) {
                const navHeight = scrolled ? 100 : 80;
                const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
                const offsetPosition = elementPosition - navHeight - 20;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        }
    };

    const navLinks = [
        { name: 'Features', href: '#features' },
        { name: 'How it works', href: '#how-it-works' },
        { name: 'FAQs', href: '#faq' },
    ];

    return (
        <motion.nav
            className={`fixed left-0 right-0 z-50 flex justify-center transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${scrolled ? 'top-6' : 'top-0'}`}
            initial={{ y: -100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
            <div
                className={`flex items-center justify-between relative transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${scrolled
                    ? 'w-[90%] max-w-5xl rounded-full bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl border border-black/5 dark:border-white/10 py-1 px-4 shadow-2xl shadow-violet-500/10'
                    : 'w-full max-w-7xl mx-auto px-4 py-2 bg-transparent border-none'
                    }`}
            >
                {/* Logo */}
                <Link to="/" className="flex items-center gap-2 group z-10 shrink-0">
                    <img
                        src="/DarkLogo.png"
                        alt="MAIRA Logo"
                        className="h-20 w-auto object-contain transition-transform duration-300 group-hover:scale-105 block dark:hidden"
                    />
                    <img
                        src="/Logo.png"
                        alt="MAIRA Logo"
                        className="h-20 w-auto object-contain transition-transform duration-300 group-hover:scale-105 hidden dark:block"
                    />
                </Link>

                {/* Desktop Links - Centered Absolutely (Nudged slightly left for visual balance) */}
                <div className="hidden md:flex items-center gap-8 absolute left-[49%] top-1/2 -translate-x-1/2 -translate-y-1/2">
                    {navLinks.map((link) => (
                        link.href.startsWith('/') ? (
                            <Link
                                key={link.name}
                                to={link.href}
                                className="text-sm font-medium text-black dark:text-neutral-400 hover:text-violet-600 dark:hover:text-white transition-colors relative group"
                            >
                                {link.name}
                                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-violet-500 transition-all group-hover:w-full" />
                            </Link>
                        ) : (
                            <a
                                key={link.name}
                                href={link.href}
                                className="text-sm font-medium text-black dark:text-neutral-400 hover:text-violet-600 dark:hover:text-white transition-colors relative group"
                                onClick={(e) => handleScrollToSection(e, link.href)}
                            >
                                {link.name}
                                <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-violet-500 transition-all group-hover:w-full" />
                            </a>
                        )
                    ))}
                </div>

                {/* Auth Buttons */}
                <div className="hidden md:flex items-center gap-4 z-10">
                    <ThemeToggle />
                    {user ? (
                        <>
                            <Link
                                to="/chat"
                                className="px-4 py-2 rounded-full bg-black/5 dark:bg-white/5 border border-neutral-200 dark:border-white/10 text-black dark:text-white text-sm font-medium hover:bg-black/10 dark:hover:bg-white/10 transition-all"
                            >
                                Chat with MAIRA
                            </Link>
                            <button
                                onClick={() => signOut()}
                                className="text-sm font-medium text-black dark:text-neutral-400 hover:text-violet-600 dark:hover:text-white transition-colors"
                            >
                                Sign Out
                            </button>
                        </>
                    ) : (
                        <>
                            <Link
                                to="/login"
                                className="text-sm font-medium text-black dark:text-neutral-400 hover:text-violet-600 dark:hover:text-white transition-colors"
                            >
                                Login
                            </Link>
                            <Link
                                to="/signup"
                                className="group relative px-5 py-2.5 rounded-full bg-black dark:bg-white text-white dark:text-black text-sm font-bold hover:shadow-[0_0_20px_rgba(0,0,0,0.3)] dark:hover:shadow-[0_0_20px_rgba(255,255,255,0.3)] transition-all overflow-hidden"
                            >
                                <span className="relative z-10">Get Started</span>
                                <div className="absolute inset-0 bg-gradient-to-r from-violet-200 to-indigo-200 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                            </Link>
                        </>
                    )}
                </div>

                {/* Mobile Menu Button */}
                <button
                    className="md:hidden text-black dark:text-white p-2"
                    onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                >
                    {mobileMenuOpen ? <X /> : <Menu />}
                </button>
            </div>

            {/* Mobile Menu */}
            <AnimatePresence>
                {mobileMenuOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="md:hidden bg-white/95 dark:bg-black/95 backdrop-blur-xl border-b border-neutral-200 dark:border-white/10 overflow-hidden"
                    >
                        <div className="px-6 py-8 flex flex-col gap-6">
                            {navLinks.map((link) => (
                                link.href.startsWith('/') ? (
                                    <Link
                                        key={link.name}
                                        to={link.href}
                                        className="text-lg font-medium text-black dark:text-neutral-300 hover:text-violet-600 dark:hover:text-white"
                                        onClick={() => setMobileMenuOpen(false)}
                                    >
                                        {link.name}
                                    </Link>
                                ) : (
                                    <a
                                        key={link.name}
                                        href={link.href}
                                        className="text-lg font-medium text-black dark:text-neutral-300 hover:text-violet-600 dark:hover:text-white"
                                        onClick={(e) => {
                                            handleScrollToSection(e, link.href);
                                            setMobileMenuOpen(false);
                                        }}
                                    >
                                        {link.name}
                                    </a>
                                )
                            ))}
                            <hr className="border-neutral-200 dark:border-white/10" />
                            {!user ? (
                                <div className="flex flex-col gap-4">
                                    <Link
                                        to="/login"
                                        className="text-lg font-medium text-black dark:text-neutral-300 hover:text-violet-600 dark:hover:text-white"
                                        onClick={() => setMobileMenuOpen(false)}
                                    >
                                        Login
                                    </Link>
                                    <Link
                                        to="/signup"
                                        className="w-full text-center px-6 py-3 rounded-full bg-black dark:bg-white text-white dark:text-black font-bold"
                                        onClick={() => setMobileMenuOpen(false)}
                                    >
                                        Get Started
                                    </Link>
                                </div>
                            ) : (
                                <div className="flex flex-col gap-4">
                                    <Link
                                        to="/chat"
                                        className="w-full text-center px-6 py-3 rounded-full bg-violet-600 text-white font-bold"
                                        onClick={() => setMobileMenuOpen(false)}
                                    >
                                        Go to Dashboard
                                    </Link>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.nav>
    );
};
