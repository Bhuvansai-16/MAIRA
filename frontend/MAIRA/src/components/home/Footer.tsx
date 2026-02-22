
import { Twitter, Github, Linkedin } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Footer = () => {
    return (
        <footer className="pt-24 pb-12 border-t border-neutral-200 dark:border-white/5 bg-white dark:bg-black text-black dark:text-neutral-400">
            <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-4 gap-12">

                {/* Brand */}
                <div className="md:col-span-1">
                    <Link to="/" className="flex items-center gap-2 mb-6 text-black dark:text-white group">
                        <img src="/DarkLogo.png" alt="MAIRA" className="h-35 w-auto object-contain transition-transform duration-300 group-hover:scale-105 block dark:hidden" />
                        <img src="/Logo.png" alt="MAIRA" className="h-35 w-auto object-contain transition-transform duration-300 group-hover:scale-105 hidden dark:block" />
                    </Link>
                    <p className="text-sm leading-relaxed mb-6 text-black dark:text-neutral-500">
                        The ultimate AI research workspace.
                        Replace generic tools with purpose-built intelligence.
                    </p>
                    <div className="flex gap-4">
                        {[Twitter, Github, Linkedin].map((Icon, i) => (
                            <a
                                key={i}
                                href="#"
                                className="p-2 rounded-full bg-neutral-100 dark:bg-white/5 hover:bg-neutral-200 dark:hover:bg-white/10 hover:text-black dark:hover:text-white transition-colors"
                            >
                                <Icon className="w-4 h-4" />
                            </a>
                        ))}
                    </div>
                </div>

                {/* Links */}
                {[
                    { title: "Product", links: ["Features", "Pricing", "Enterprise", "Case Studies"] },
                    { title: "Resources", links: ["Docs", "API", "Blog", "Community"] },
                    { title: "Company", links: ["About", "Careers", "Legal", "Contact"] }
                ].map((section, idx) => (
                    <div key={idx}>
                        <h4 className="font-bold text-black dark:text-white mb-6 uppercase tracking-wider text-xs">{section.title}</h4>
                        <ul className="space-y-4 text-sm">
                            {section.links.map((link) => (
                                <li key={link}>
                                    <a href="#" className="hover:text-violet-400 transition-colors block py-1">
                                        {link}
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </div>
                ))}
            </div>

            <div className="max-w-7xl mx-auto px-6 mt-20 pt-8 border-t border-neutral-200 dark:border-white/5 flex flex-col md:flex-row justify-between items-center text-xs text-black dark:text-neutral-600">
                <p>&copy; 2026 MAIRA Research Inc. All rights reserved.</p>
                <div className="flex gap-8 mt-4 md:mt-0">
                    <a href="#" className="hover:text-black dark:hover:text-white transition-colors">Privacy Policy</a>
                    <a href="#" className="hover:text-black dark:hover:text-white transition-colors">Terms of Service</a>
                </div>
            </div>
        </footer>
    );
};
