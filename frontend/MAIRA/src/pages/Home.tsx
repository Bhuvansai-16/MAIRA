import { Navbar } from '../components/home/Navbar';
import { Hero } from '../components/home/Hero';
import { FeatureGrid } from '../components/home/FeatureGrid';
import { Process } from '../components/home/Process';
import { FAQ } from '../components/home/FAQ';
import { Footer } from '../components/home/Footer';
import { useAuth } from '../context/AuthContext';
import { HomeSkeleton } from '../components/skeletons/HomeSkeleton';
import { useEffect, useState } from 'react';

export const Home = () => {
    const { loading } = useAuth();
    const [showSkeleton, setShowSkeleton] = useState(true);

    useEffect(() => {
        if (!loading) {
            // Optional: minimal delay to ensure smooth transition or if loading is too fast
            const timer = setTimeout(() => setShowSkeleton(false), 500);
            return () => clearTimeout(timer);
        }
    }, [loading]);

    if (showSkeleton) {
        return <HomeSkeleton />;
    }

    return (
        <div className="min-h-screen bg-white dark:bg-black text-black dark:text-white overflow-x-hidden selection:bg-violet-500/30">
            <Navbar />

            <main>
                <Hero />
                <FeatureGrid />
                <Process />


                <FAQ />
            </main>

            <Footer />
        </div>
    );
};
