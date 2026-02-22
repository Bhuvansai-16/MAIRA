
import { Moon, Sun } from "lucide-react"
import { useTheme } from "../context/ThemeContext"
import { motion } from "framer-motion"

export function ThemeToggle() {
    const { theme, setTheme } = useTheme()

    return (
        <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="relative p-2 rounded-full text-neutral-400 hover:text-white hover:bg-white/10 transition-colors"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
            <div className="relative w-5 h-5">
                <motion.div
                    initial={false}
                    animate={{ scale: theme === "dark" ? 1 : 0, rotate: theme === "dark" ? 0 : 90 }}
                    transition={{ duration: 0.2 }}
                    className="absolute inset-0 flex items-center justify-center"
                >
                    <Moon size={20} />
                </motion.div>

                <motion.div
                    initial={false}
                    animate={{ scale: theme === "light" ? 1 : 0, rotate: theme === "light" ? 0 : -90 }}
                    transition={{ duration: 0.2 }}
                    className="absolute inset-0 flex items-center justify-center"
                >
                    <Sun size={20} />
                </motion.div>
            </div>
        </button>
    )
}
